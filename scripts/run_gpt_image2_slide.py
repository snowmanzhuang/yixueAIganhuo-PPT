#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import http.client
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

try:
    import requests
except ImportError:  # pragma: no cover - urllib fallback remains below
    requests = None


PROVIDER_DEFAULTS = {
    "openai_api": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "api_key_fallback": None,
    },
    "openai_compatible": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "api_key_fallback": None,
    },
    "local_cliproxyapi": {
        "base_url": "http://127.0.0.1:8317/v1",
        "api_key_env": "CLIPROXYAPI_KEY",
        "api_key_fallback": "your-api-key-1",
    },
}


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --prompt, --prompt-file, or stdin prompt text.")


def image_to_data_url(path: str) -> str:
    image_path = Path(path).expanduser().resolve()
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def resolve_provider(args: argparse.Namespace) -> tuple[str, str]:
    defaults = PROVIDER_DEFAULTS[args.provider_kind]
    base_url = args.base_url or defaults["base_url"]
    if not base_url:
        raise SystemExit("--base-url is required for openai_compatible provider mode.")

    api_key_env = args.api_key_env or defaults["api_key_env"]
    api_key = args.api_key or os.environ.get(api_key_env) or defaults["api_key_fallback"]
    if not api_key:
        raise SystemExit(f"Missing API key. Set {api_key_env} or pass --api-key.")
    return base_url.rstrip("/"), api_key


def write_image_url(image_url: str, out: Path, timeout: int) -> None:
    if image_url.startswith("data:"):
        _, encoded = image_url.split(",", 1)
        out.write_bytes(base64.b64decode(encoded))
        return
    with urllib.request.urlopen(image_url, timeout=timeout) as img:
        out.write_bytes(img.read())


def decode_image_response(data: dict, out: Path, timeout: int) -> None:
    try:
        item = data["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected image response: {data}") from exc

    if "b64_json" in item:
        out.write_bytes(base64.b64decode(item["b64_json"]))
        return
    if "url" in item:
        write_image_url(item["url"], out, timeout)
        return
    raise RuntimeError(f"Unexpected image response item keys: {list(item.keys())}")


def decode_openrouter_chat_image_response(data: dict, out: Path, timeout: int) -> None:
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter chat response: {data}") from exc

    for image in message.get("images") or []:
        image_url = image.get("image_url", {}).get("url")
        if image_url:
            write_image_url(image_url, out, timeout)
            return

    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            image_url = part.get("image_url", {}).get("url") if isinstance(part, dict) else None
            if image_url:
                write_image_url(image_url, out, timeout)
                return

    raise RuntimeError(f"OpenRouter chat response did not contain message.images: {data}")


def is_openrouter_chat_provider(args: argparse.Namespace, base_url: str) -> bool:
    return args.provider_kind == "openai_compatible" and "openrouter.ai" in base_url


def size_tuple(size: str) -> tuple[int, int]:
    try:
        width, height = size.lower().split("x", 1)
        return int(width), int(height)
    except ValueError as exc:
        raise SystemExit(f"Invalid --size value: {size}. Expected WIDTHxHEIGHT, for example 2560x1440.") from exc


def size_instruction(size: str) -> str:
    width, height = size_tuple(size)
    return (
        f"\n\nTarget canvas: {width}x{height} pixels, "
        f"16:9 widescreen PowerPoint slide canvas. Do not return a square image."
    )


def openrouter_size_instruction() -> str:
    return "\n\nTarget canvas: 2560x1440 pixels, 16:9 widescreen PowerPoint slide canvas. Do not return a square image."


def aspect_ratio_for(size: str) -> str:
    width, height = size_tuple(size)
    if width * 9 == height * 16:
        return "16:9"
    return f"{width}:{height}"


def openrouter_chat_payload(args: argparse.Namespace, prompt: str) -> dict:
    if args.image:
        content = [{"type": "text", "text": prompt + openrouter_size_instruction()}]
        for path in args.image:
            content.append({"type": "image_url", "image_url": image_to_data_url(path)})
    else:
        content = prompt + openrouter_size_instruction()
    return {
        "model": args.model,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
        "stream": False,
        "image_config": {
            "image_size": "2K",
            "aspect_ratio": "16:9",
        },
    }


def validate_output_size(out: Path, size: str, *, provider_kind: str, base_url: str) -> None:
    expected = (2560, 1440) if provider_kind == "openai_compatible" and "openrouter.ai" in base_url else size_tuple(size)
    with Image.open(out) as image:
        actual = image.size
    if actual == expected:
        return
    if provider_kind == "openai_compatible" and "openrouter.ai" in base_url:
        raise SystemExit(f"Generated image has size {actual}, expected {expected}. OpenRouter must return 2560x1440 for this workflow.")
    raise SystemExit(f"Generated image has size {actual}, expected {expected}. Provider did not honor --size {size}.")


def post_json_with_retries(req: urllib.request.Request, *, timeout: int, retries: int, base_url: str, endpoint: str) -> dict:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            if requests is not None:
                json_payload = json.loads((req.data or b"{}").decode("utf-8"))
                request_headers = dict(req.header_items())
                request_headers.pop("Content-type", None)
                request_headers.pop("Content-Type", None)
                resp = requests.post(
                    req.full_url,
                    json=json_payload,
                    headers=request_headers,
                    timeout=(20, timeout),
                )
                body = resp.text
                if resp.status_code >= 400:
                    if resp.status_code not in {408, 409, 425, 429, 500, 502, 503, 504} or attempt == retries:
                        print(resp.status_code, file=sys.stderr)
                        print(body, file=sys.stderr)
                        raise SystemExit(1)
                    last_error = f"HTTP {resp.status_code}: {body[:300]}"
                    raise RuntimeError(last_error)
                return json.loads(body)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                return json.loads(body)
        except RuntimeError:
            if attempt == retries:
                raise SystemExit(1)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            if exc.code not in {408, 409, 425, 429, 500, 502, 503, 504} or attempt == retries:
                print(exc.code, file=sys.stderr)
                print(body, file=sys.stderr)
                raise SystemExit(1) from exc
            last_error = f"HTTP {exc.code}: {body[:300]}"
        except urllib.error.URLError as exc:
            if attempt == retries:
                print(f"Could not connect to {base_url}: {exc.reason}", file=sys.stderr)
                raise SystemExit(1) from exc
            last_error = f"URL error: {exc.reason}"
        except requests.exceptions.RequestException as exc:
            if attempt == retries:
                print(f"Could not connect to {base_url}: {exc}", file=sys.stderr)
                raise SystemExit(1) from exc
            last_error = f"requests error: {exc}"
        except http.client.IncompleteRead as exc:
            if attempt == retries:
                print(f"Incomplete response from {base_url}{endpoint}: {exc}", file=sys.stderr)
                partial = getattr(exc, "partial", b"") or b""
                if partial:
                    preview = partial[:800].decode("utf-8", "replace")
                    print(f"Partial response preview: {preview}", file=sys.stderr)
                raise SystemExit(1) from exc
            last_error = f"Incomplete response: {exc}"
        except json.JSONDecodeError as exc:
            if attempt == retries:
                print(f"Provider returned non-JSON response from {base_url}{endpoint}.", file=sys.stderr)
                raise SystemExit(1) from exc
            last_error = f"JSON decode error: {exc}"
        wait_seconds = min(2 ** (attempt - 1), 8)
        print(f"Attempt {attempt}/{retries} failed ({last_error}); retrying in {wait_seconds}s.", file=sys.stderr)
        time.sleep(wait_seconds)
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one GPT Image 2 PPT slide image through OpenAI, OpenAI-compatible, or local CLIProxyAPI providers.")
    parser.add_argument("--provider-kind", choices=sorted(PROVIDER_DEFAULTS), default="openai_api")
    parser.add_argument("--prompt", help="Prompt text for image generation")
    parser.add_argument("--prompt-file", help="UTF-8 text file containing the prompt")
    parser.add_argument("--out", required=True, help="Output image path, usually .png")
    parser.add_argument("--image", action="append", default=[], help="Input/reference image path. Repeat for multiple images. Uses /v1/images/edits.")
    parser.add_argument("--size", default="2560x1440", help="Image size, default: 2560x1440")
    parser.add_argument("--model", default="gpt-image-2", help="Image model, default: gpt-image-2")
    parser.add_argument("--base-url", help="Provider base URL ending before /images, for example https://api.openai.com/v1")
    parser.add_argument("--api-key-env", help="Environment variable containing the API key")
    parser.add_argument("--api-key", help="API key. Prefer environment variables instead of passing secrets on the command line.")
    parser.add_argument("--timeout", type=int, default=600, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=3, help="Provider request attempts for transient network, rate-limit, and 5xx failures")
    args = parser.parse_args()

    prompt = load_prompt(args).strip()
    if not prompt:
        raise SystemExit("Prompt is empty.")

    base_url, api_key = resolve_provider(args)
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if is_openrouter_chat_provider(args, base_url):
        endpoint = "/chat/completions"
        payload = openrouter_chat_payload(args, prompt)
    else:
        endpoint = "/images/generations"
        payload = {
            "model": args.model,
            "prompt": prompt,
            "size": args.size,
            "response_format": "b64_json",
        }
        if args.image:
            endpoint = "/images/edits"
            payload["images"] = [{"image_url": image_to_data_url(path)} for path in args.image]

    req = urllib.request.Request(
        f"{base_url}{endpoint}",
        data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    data = post_json_with_retries(req, timeout=args.timeout, retries=args.retries, base_url=base_url, endpoint=endpoint)

    if is_openrouter_chat_provider(args, base_url):
        decode_openrouter_chat_image_response(data, out, args.timeout)
    else:
        decode_image_response(data, out, args.timeout)
    validate_output_size(out, args.size, provider_kind=args.provider_kind, base_url=base_url)
    print(out)


if __name__ == "__main__":
    main()
