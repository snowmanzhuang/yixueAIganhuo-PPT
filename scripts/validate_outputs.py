#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image
from pptx import Presentation


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated slide/editable pipeline outputs.")
    parser.add_argument("--manifest")
    parser.add_argument("--slides-dir", required=True)
    parser.add_argument("--ocr-dir", required=True)
    parser.add_argument("--clean-dir", required=True)
    parser.add_argument("--pptx", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    slides_dir = Path(args.slides_dir)
    ocr_dir = Path(args.ocr_dir)
    clean_dir = Path(args.clean_dir)
    pptx = Path(args.pptx)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    slide_images = sorted(slides_dir.glob("slide*.png"))
    ocr_jsons = sorted(ocr_dir.glob("slide*_ocr.json"))
    clean_images = sorted(clean_dir.glob("slide*_clean_background.png"))
    issues = []

    expected_size = (2560, 1440)
    for slide_image in slide_images:
        with Image.open(slide_image) as im:
            if im.size != expected_size:
                issues.append(f"Unexpected slide image size for {slide_image}: {im.size}")

    for clean in clean_images:
        with Image.open(clean) as im:
            if im.size != expected_size:
                issues.append(f"Unexpected clean background size for {clean}: {im.size}")

    pptx_slide_count = None
    if pptx.exists():
        prs = Presentation(str(pptx))
        pptx_slide_count = len(prs.slides)
    else:
        issues.append(f"Missing PPTX: {pptx}")

    if pptx_slide_count is not None and pptx_slide_count != len(clean_images):
        issues.append(f"PPTX slide count {pptx_slide_count} != clean backgrounds {len(clean_images)}")

    report = {
        "slides": len(slide_images),
        "ocr_jsons": len(ocr_jsons),
        "clean_backgrounds": len(clean_images),
        "pptx": str(pptx),
        "pptx_slide_count": pptx_slide_count,
        "issues": issues,
        "passed": not issues,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
