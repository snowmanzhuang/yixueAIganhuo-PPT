#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REEXEC_MARKER = "GPT_IMAGE2_PPTX_OCR_REEXECED"


def load_provider_config(path: str | None) -> dict:
    if not path:
        return {}
    config_path = Path(path).expanduser()
    if not config_path.exists():
        raise SystemExit(f"Provider config not found: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return data.get("ocr_provider", data)


def env_flag_enabled(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def resolve_ocr_python(provider: dict) -> str | None:
    return os.environ.get("PADDLEOCR_PYTHON") or provider.get("python")


def same_executable(left: str, right: str) -> bool:
    try:
        return Path(left).resolve() == Path(right).expanduser().resolve()
    except OSError:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(os.path.expanduser(right)))


def maybe_reexec_into_configured_python() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--provider-config")
    known, _ = parser.parse_known_args()
    provider = load_provider_config(known.provider_config)
    ocr_python = resolve_ocr_python(provider)
    if provider.get("disable_model_source_check") or env_flag_enabled("PADDLEOCR_DISABLE_MODEL_SOURCE_CHECK"):
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    if not ocr_python or os.environ.get(REEXEC_MARKER) == "1" or same_executable(sys.executable, ocr_python):
        return
    target = Path(ocr_python).expanduser()
    if not target.exists():
        raise SystemExit(f"Configured PaddleOCR Python does not exist: {target}")
    env = os.environ.copy()
    env[REEXEC_MARKER] = "1"
    os.execve(str(target), [str(target), *sys.argv], env)


def import_paddleocr():
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise SystemExit(
            "PaddleOCR is not importable in the active Python environment. "
            "Set PADDLEOCR_PYTHON to the PaddleOCR venv Python executable, or pass "
            "--provider-config with ocr_provider.python."
        ) from exc
    return PaddleOCR


def normalize_result(result):
    items = []
    for page in result:
        if isinstance(page, dict):
            texts = page.get("rec_texts") or []
            scores = page.get("rec_scores") or []
            polys = page.get("rec_polys") or page.get("dt_polys") or []
            for text, score, poly in zip(texts, scores, polys):
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


def main() -> None:
    maybe_reexec_into_configured_python()
    PaddleOCR = import_paddleocr()

    parser = argparse.ArgumentParser(description="Run local PP-OCRv5 on one slide image.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--ocr-json", required=True)
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--provider-config", help="JSON config containing ocr_provider.python and optional OCR settings")
    parser.add_argument("--lang")
    parser.add_argument("--det-model")
    parser.add_argument("--rec-model")
    args = parser.parse_args()

    provider = load_provider_config(args.provider_config)
    image_path = Path(args.image)
    ocr_json = Path(args.ocr_json)
    annotation = Path(args.annotation)
    ocr_json.parent.mkdir(parents=True, exist_ok=True)

    ocr = PaddleOCR(
        lang=args.lang or provider.get("lang", "ch"),
        ocr_version="PP-OCRv5",
        text_detection_model_name=args.det_model or provider.get("det_model", "PP-OCRv5_server_det"),
        text_recognition_model_name=args.rec_model or provider.get("rec_model", "PP-OCRv5_server_rec"),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    result = ocr.predict(str(image_path))
    items = normalize_result(result)
    ocr_json.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    annotate(image_path, items, annotation)
    print(json.dumps({"image": str(image_path), "ocr_json": str(ocr_json), "annotation": str(annotation), "items": len(items), "python": sys.executable}, ensure_ascii=False))


if __name__ == "__main__":
    main()
