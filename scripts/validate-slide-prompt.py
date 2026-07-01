#!/usr/bin/env python3
"""Validate a rich GPT Image 2 slide prompt before image-worker dispatch."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MIN_PROMPT_CHARS = 900
MIN_STYLE_KEY_COUNT = 3
MIN_LINE_COUNT = 18


STYLE_KEY_RE = re.compile(
    r"\[(?:global|continuity|illustration|asset_embedding|closing|negative_constraints)\.[^\]]+\]"
)


def read_prompt(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return None, f"prompt does not exist: {path}"
    except UnicodeDecodeError as exc:
        return None, f"prompt is not UTF-8 text: {path}: {exc}"


def count_negative_terms(text: str) -> int:
    return len(re.findall(r"不要|禁止|不得|Do not|No ", text, flags=re.IGNORECASE))


def continuity_ok(text: str, slide_number: int) -> bool:
    lowered = text.casefold()
    if slide_number <= 1:
        return "母版" in text or "visual template" in lowered or "master" in lowered
    if slide_number == 2:
        return "slide01" in lowered or "第 1 页" in text or "第1页" in text
    return (
        ("slide01" in lowered or "第 1 页" in text or "第1页" in text)
        and ("slide02" in lowered or "第 2 页" in text or "第2页" in text)
    )


def validate(prompt: Path, slide_number: int) -> dict[str, Any]:
    errors: list[str] = []
    checks = {
        "prompt_exists": False,
        "min_length": False,
        "gpt_image_instruction": False,
        "style_key_expansion": False,
        "slide_plan": False,
        "layout_geometry": False,
        "evidence_or_asset_binding": False,
        "negative_constraints": False,
        "continuity": False,
        "not_summary_only": False,
    }

    text, read_error = read_prompt(prompt)
    if read_error:
        errors.append(read_error)
        return {
            "passed": False,
            "prompt": str(prompt),
            "slide_number": slide_number,
            "checks": checks,
            "metrics": {},
            "errors": errors,
        }

    assert text is not None
    style_key_count = len(STYLE_KEY_RE.findall(text))
    line_count = len([line for line in text.splitlines() if line.strip()])
    negative_count = count_negative_terms(text)
    lowered = text.casefold()

    checks["prompt_exists"] = True
    checks["min_length"] = len(text) >= MIN_PROMPT_CHARS
    checks["gpt_image_instruction"] = (
        "gpt image 2" in lowered
        and "16:9" in text
        and ("ppt" in lowered or "powerpoint" in lowered)
    )
    checks["style_key_expansion"] = style_key_count >= MIN_STYLE_KEY_COUNT
    checks["slide_plan"] = (
        ("本页 PPT 计划" in text or "slide plan" in lowered)
        and ("slide_id" in text or "slide_number" in text)
        and ("core_message" in text or "title" in text)
    )
    checks["layout_geometry"] = (
        ("布局" in text or "layout" in lowered)
        and ("证据" in text or "evidence" in lowered or "region" in lowered)
    )
    checks["evidence_or_asset_binding"] = any(
        term in lowered for term in ["figure", "asset", "evidence"]
    ) or any(term in text for term in ["原始图片", "证据", "医学影像", "论文图"])
    checks["negative_constraints"] = negative_count >= 3
    checks["continuity"] = continuity_ok(text, slide_number)
    checks["not_summary_only"] = line_count >= MIN_LINE_COUNT and checks["min_length"]

    if not checks["min_length"]:
        errors.append(f"prompt is too short for rich GPT Image 2 slide generation: {len(text)} chars")
    if not checks["gpt_image_instruction"]:
        errors.append("prompt must explicitly target GPT Image 2 and a complete 16:9 PowerPoint/PPT page")
    if not checks["style_key_expansion"]:
        errors.append("prompt must include expanded style key sections, not a short style summary")
    if not checks["slide_plan"]:
        errors.append("prompt must include the slide-specific plan from ppt_plan.json")
    if not checks["layout_geometry"]:
        errors.append("prompt must include concrete layout geometry and evidence/region instructions")
    if not checks["evidence_or_asset_binding"]:
        errors.append("prompt must include evidence, Figure, or asset binding instructions")
    if not checks["negative_constraints"]:
        errors.append("prompt must include explicit negative constraints")
    if not checks["continuity"]:
        errors.append("prompt must include slide continuity or master-template instructions")
    if not checks["not_summary_only"]:
        errors.append("prompt appears summary-style rather than a complete generation prompt")

    passed = not errors and all(checks.values())
    return {
        "passed": passed,
        "prompt": str(prompt),
        "slide_number": slide_number,
        "checks": checks,
        "metrics": {
            "chars": len(text),
            "nonempty_lines": line_count,
            "style_key_count": style_key_count,
            "negative_term_count": negative_count,
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Path to prompts/slideNN.txt")
    parser.add_argument("--slide-number", required=True, type=int)
    args = parser.parse_args()

    payload = validate(Path(args.prompt), args.slide_number)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
