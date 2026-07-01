#!/usr/bin/env python3
"""Preflight a generated slide image before editppt prepare/add-page."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


EXPECTED_STATUS = "IMAGE_READY"
EXPECTED_TOOL_FRAGMENT = "editppt image"
MIN_DIMENSION = 720
ASPECT_RATIO = 16 / 9
ASPECT_TOLERANCE = 0.03
MIN_STDDEV = 6.0
MIN_NON_WHITE_FRACTION = 0.002


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"slide result does not exist: {path}"
    except json.JSONDecodeError as exc:
        return None, f"slide result is not valid JSON: {path}: {exc}"


def is_sources_placeholder_path(path: Path) -> bool:
    parts = [part.casefold() for part in path.parts]
    return any(parts[index : index + 2] == ["slides", "sources"] for index in range(len(parts) - 1))


def image_metrics(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            sample = rgb.copy()
            sample.thumbnail((512, 512))
            stat = ImageStat.Stat(sample)
            stddev = max(stat.stddev) if stat.stddev else 0.0
            grayscale = sample.convert("L")
            pixels = list(grayscale.getdata())
            non_white = sum(1 for value in pixels if value < 248)
            non_white_fraction = non_white / len(pixels) if pixels else 0.0
            return {
                "width": width,
                "height": height,
                "aspect_ratio": width / height if height else None,
                "max_channel_stddev": stddev,
                "non_white_fraction": non_white_fraction,
            }, None
    except FileNotFoundError:
        return None, f"slide image does not exist: {path}"
    except Exception as exc:  # PIL raises several concrete exception types.
        return None, f"slide image cannot be opened as an image: {path}: {exc}"


def result_output_matches(result: dict[str, Any], slide: Path) -> bool:
    output = result.get("output")
    if not output:
        return False
    output_path = Path(str(output))
    try:
        return output_path.resolve() == slide.resolve()
    except FileNotFoundError:
        return output_path == slide


def validate(slide: Path, result_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    checks = {
        "slide_exists": False,
        "result_exists": False,
        "status": False,
        "passed": False,
        "provenance": False,
        "output_matches_slide": False,
        "dimensions": False,
        "aspect_ratio": False,
        "nonblank": False,
        "not_sources_placeholder": False,
    }

    result, result_error = load_json(result_path)
    if result_error:
        errors.append(result_error)
    else:
        assert result is not None
        checks["result_exists"] = True
        checks["status"] = result.get("status") == EXPECTED_STATUS
        checks["passed"] = result.get("passed") is True
        backend = result.get("image_backend") or {}
        tool_call = str(backend.get("tool_call", ""))
        checks["provenance"] = EXPECTED_TOOL_FRAGMENT in tool_call
        checks["output_matches_slide"] = result_output_matches(result, slide)

        if not checks["status"]:
            errors.append(f"slide result status must be {EXPECTED_STATUS}")
        if not checks["passed"]:
            errors.append("slide result passed must be true")
        if not checks["provenance"]:
            errors.append("slide result provenance must show editppt image generate/edit/batch")
        if not checks["output_matches_slide"]:
            errors.append("slide result output must point to the validated slide image")

    metrics, image_error = image_metrics(slide)
    if image_error:
        errors.append(image_error)
    else:
        assert metrics is not None
        checks["slide_exists"] = True
        width = metrics["width"]
        height = metrics["height"]
        aspect = metrics["aspect_ratio"]
        checks["dimensions"] = width >= MIN_DIMENSION and height >= MIN_DIMENSION
        checks["aspect_ratio"] = aspect is not None and math.isclose(
            float(aspect), ASPECT_RATIO, rel_tol=ASPECT_TOLERANCE
        )
        checks["nonblank"] = (
            float(metrics["max_channel_stddev"]) >= MIN_STDDEV
            and float(metrics["non_white_fraction"]) >= MIN_NON_WHITE_FRACTION
        )

        if not checks["dimensions"]:
            errors.append(f"slide image dimensions are too small: {width}x{height}")
        if not checks["aspect_ratio"]:
            errors.append(f"slide image must be 16:9, got {width}x{height}")
        if not checks["nonblank"]:
            errors.append("slide image appears blank, solid-color, or low-variance placeholder")

    checks["not_sources_placeholder"] = not is_sources_placeholder_path(slide)
    if not checks["not_sources_placeholder"]:
        errors.append("slides/sources paths are reserved for source assets, not generated slide images")

    passed = not errors and all(checks.values())
    return {
        "passed": passed,
        "slide": str(slide),
        "result": str(result_path),
        "checks": checks,
        "metrics": metrics or {},
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slide", required=True, help="Path to generated slides/slideNN.png")
    parser.add_argument("--result", required=True, help="Path to slide_results/slideNN.json")
    args = parser.parse_args()

    payload = validate(Path(args.slide), Path(args.result))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
