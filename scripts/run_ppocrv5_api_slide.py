#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

DEFAULT_JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
DEFAULT_MODEL = "PP-OCRv5"


def submit_job(
    *,
    image: str,
    job_url: str,
    token: str,
    model: str,
    optional_payload: dict,
    timeout: int,
) -> str:
    headers = {"Authorization": f"bearer {token}"}
    if image.startswith("http://") or image.startswith("https://"):
        headers["Content-Type"] = "application/json"
        payload = {
            "fileUrl": image,
            "model": model,
            "optionalPayload": optional_payload,
        }
        response = requests.post(job_url, json=payload, headers=headers, timeout=timeout)
    else:
        image_path = Path(image).expanduser()
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        data = {
            "model": model,
            "optionalPayload": json.dumps(optional_payload),
        }
        with image_path.open("rb") as file:
            response = requests.post(job_url, headers=headers, data=data, files={"file": file}, timeout=timeout)

    if response.status_code != 200:
        raise RuntimeError(f"PP-OCRv5 API submit failed: {response.status_code} {response.text}")
    payload = response.json()
    try:
        return payload["data"]["jobId"]
    except KeyError as exc:
        raise RuntimeError(f"Unexpected PP-OCRv5 API submit response: {payload}") from exc


def poll_result_url(*, job_url: str, token: str, job_id: str, poll_interval: int, timeout: int) -> str:
    headers = {"Authorization": f"bearer {token}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = requests.get(f"{job_url.rstrip('/')}/{job_id}", headers=headers, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"PP-OCRv5 API poll failed: {response.status_code} {response.text}")
        payload = response.json()
        data = payload.get("data", {})
        state = data.get("state")
        if state == "done":
            try:
                return data["resultUrl"]["jsonUrl"]
            except KeyError as exc:
                raise RuntimeError(f"PP-OCRv5 API done response missing jsonUrl: {payload}") from exc
        if state == "failed":
            raise RuntimeError(f"PP-OCRv5 API job failed: {data.get('errorMsg', payload)}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Timed out waiting for PP-OCRv5 API job {job_id}")


def load_first_ocr_result(jsonl_url: str, timeout: int) -> dict:
    response = requests.get(jsonl_url, timeout=timeout)
    response.raise_for_status()
    for line in response.text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        results = payload.get("result", {}).get("ocrResults", [])
        if results:
            return results[0]
    raise RuntimeError("PP-OCRv5 API JSONL did not contain result.ocrResults")


def normalize_result(result: dict) -> list[dict]:
    pruned = result.get("prunedResult", result)
    texts = pruned.get("rec_texts") or []
    scores = pruned.get("rec_scores") or []
    polys = pruned.get("rec_polys") or pruned.get("dt_polys") or []
    items = []
    for text, score, poly in zip(texts, scores, polys):
        text = str(text).strip()
        if not text:
            continue
        pts = [[float(x), float(y)] for x, y in poly]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        items.append({
            "text": text,
            "score": float(score),
            "poly": pts,
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
        })
    return items


def annotate(image_path: Path, items: list[dict], out_path: Path) -> None:
    im = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(im)
    for i, item in enumerate(items, 1):
        x1, y1, x2, y2 = item["bbox"]
        color = "green" if item["score"] >= 0.72 else "red"
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3 if color == "green" else 2)
        draw.text((x1, max(0, y1 - 14)), str(i), fill=color)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)


def write_raw_outputs(raw_dir: Path | None, *, job_id: str, jsonl_url: str, ocr_result: dict) -> None:
    if not raw_dir:
        return
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "job_id.txt").write_text(job_id, encoding="utf-8")
    (raw_dir / "jsonl_url.txt").write_text(jsonl_url, encoding="utf-8")
    (raw_dir / "ocr_result.json").write_text(json.dumps(ocr_result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PaddleOCR PP-OCRv5 API on one slide image and emit the same OCR JSON contract as local PP-OCRv5.")
    parser.add_argument("--image", required=True, help="Local image path or image URL")
    parser.add_argument("--ocr-json", required=True)
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--token", default=os.environ.get("AISTUDIO_OCR_TOKEN"), help="AI Studio access token; prefer AISTUDIO_OCR_TOKEN")
    parser.add_argument("--job-url", default=DEFAULT_JOB_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--raw-dir", help="Optional directory for job id and raw OCR result JSON")
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("Missing AI Studio OCR token. Set AISTUDIO_OCR_TOKEN or pass --token. Get a token at https://aistudio.baidu.com/paddleocr")

    optional_payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
    }
    job_id = submit_job(
        image=args.image,
        job_url=args.job_url,
        token=args.token,
        model=args.model,
        optional_payload=optional_payload,
        timeout=args.timeout,
    )
    jsonl_url = poll_result_url(
        job_url=args.job_url,
        token=args.token,
        job_id=job_id,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )
    ocr_result = load_first_ocr_result(jsonl_url, args.timeout)
    items = normalize_result(ocr_result)

    ocr_json = Path(args.ocr_json)
    annotation = Path(args.annotation)
    ocr_json.parent.mkdir(parents=True, exist_ok=True)
    ocr_json.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.image.startswith("http://") or args.image.startswith("https://"):
        raise SystemExit("Annotation output requires a local --image path.")
    annotate(Path(args.image), items, annotation)
    write_raw_outputs(Path(args.raw_dir) if args.raw_dir else None, job_id=job_id, jsonl_url=jsonl_url, ocr_result=ocr_result)
    print(json.dumps({"image": args.image, "ocr_json": str(ocr_json), "annotation": str(annotation), "items": len(items), "job_id": job_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
