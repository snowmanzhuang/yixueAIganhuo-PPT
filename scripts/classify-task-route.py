#!/usr/bin/env python3
"""Classify yixueAIganhuo-PPT task intent before worker dispatch."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FULL_AUTHORING_FROM_SOURCE = "FULL_AUTHORING_FROM_SOURCE"
DIRECT_VISUAL_CONVERSION = "DIRECT_VISUAL_CONVERSION"
AMBIGUOUS_INPUT = "AMBIGUOUS_INPUT"


SOURCE_PATTERNS = [
    r"\babstract\b",
    r"\bintroduction\b",
    r"\bmethods?\b",
    r"\bresults?\b",
    r"\breferences?\b",
    r"\bdoi\b",
    r"\bjournal\b",
    r"\bmanuscript\b",
    r"\bresearch\s+(paper|article|pdf|material)\b",
    r"\bclinical\s+(trial|study|guideline)\b",
    r"论文",
    r"文献",
    r"素材",
    r"资料",
    r"医学论文",
    r"研究",
    r"指南",
    r"报告",
    r"综述",
    r"病例",
    r"figure",
    r"fig\.",
]

DIRECT_PATTERNS = [
    r"已有幻灯片",
    r"现有幻灯片",
    r"幻灯片截图",
    r"图像型\s*(ppt|pptx|pdf)?",
    r"截图转",
    r"保持现有页面",
    r"保留现有页面",
    r"\bexisting\s+(visual\s+)?(slide|deck|ppt|presentation)",
    r"\bimage[- ]based\s+(deck|ppt|pptx|presentation)\b",
    r"\bscreenshot\s+(set|sequence|deck)\b",
    r"\bas[- ]is\b",
    r"\bpreserve\b",
    r"\bslide\s+pages?\b",
    r"\bdesigned\s+layouts?\b",
]

WEAK_VISUAL_FORMAT_PATTERNS = [
    r"\b16:9\b",
    r"\bwidescreen\b",
]

PDF_CONVERT_PATTERNS = [
    r"pdf\s*(转|to)\s*pptx?",
    r"转为\s*pptx?",
    r"转成\s*可编辑\s*pptx?",
    r"convert\s+.*pdf\s+.*pptx?",
]


def normalize(text: str) -> str:
    return text.casefold()


def count_matches(patterns: list[str], text: str) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE))


def has_pdf(paths: list[str]) -> bool:
    return any(Path(path).suffix.casefold() == ".pdf" for path in paths)


def classify(user_request: str, input_summary: str, paths: list[str]) -> dict:
    haystack = normalize(" ".join([user_request, input_summary, " ".join(paths)]))
    source_hits = count_matches(SOURCE_PATTERNS, haystack)
    direct_hits = count_matches(DIRECT_PATTERNS, haystack)
    weak_visual_format_hits = count_matches(WEAK_VISUAL_FORMAT_PATTERNS, haystack)
    pdf_convert_hits = count_matches(PDF_CONVERT_PATTERNS, haystack)

    if direct_hits >= 2:
        return {
            "task_route": DIRECT_VISUAL_CONVERSION,
            "should_start_with_editppt_prepare": True,
            "reason": "Input has strong evidence of an existing visual slide deck/page design to preserve as-is.",
            "source_signal_count": source_hits,
            "direct_visual_signal_count": direct_hits,
            "weak_visual_format_signal_count": weak_visual_format_hits,
            "clarification_question": "",
        }

    if source_hits:
        return {
            "task_route": FULL_AUTHORING_FROM_SOURCE,
            "should_start_with_editppt_prepare": False,
            "reason": "Input looks like medical/research source material; run full upstream authoring before page-worker conversion.",
            "source_signal_count": source_hits,
            "direct_visual_signal_count": direct_hits,
            "weak_visual_format_signal_count": weak_visual_format_hits,
            "clarification_question": "",
        }

    if direct_hits >= 1 and not pdf_convert_hits:
        return {
            "task_route": DIRECT_VISUAL_CONVERSION,
            "should_start_with_editppt_prepare": True,
            "reason": "Input looks like an existing visual slide deck/page design to preserve as-is.",
            "source_signal_count": source_hits,
            "direct_visual_signal_count": direct_hits,
            "weak_visual_format_signal_count": weak_visual_format_hits,
            "clarification_question": "",
        }

    if has_pdf(paths) and pdf_convert_hits:
        return {
            "task_route": AMBIGUOUS_INPUT,
            "should_start_with_editppt_prepare": False,
            "reason": "PDF-to-PPTX request lacks enough evidence to distinguish source material from an existing visual deck.",
            "source_signal_count": source_hits,
            "direct_visual_signal_count": direct_hits,
            "weak_visual_format_signal_count": weak_visual_format_hits,
            "clarification_question": "这份 PDF 是制作医学 PPT 的资料，还是已有幻灯片/截图需要转可编辑 PPTX？",
        }

    return {
        "task_route": FULL_AUTHORING_FROM_SOURCE,
        "should_start_with_editppt_prepare": False,
        "reason": "Defaulting to full upstream medical PPT authoring when no direct visual deck signal is present.",
        "source_signal_count": source_hits,
        "direct_visual_signal_count": direct_hits,
        "weak_visual_format_signal_count": weak_visual_format_hits,
        "clarification_question": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*", help="Input files or directories.")
    parser.add_argument("--user-request", default="", help="Original user request.")
    parser.add_argument(
        "--input-summary",
        default="",
        help="Brief text from quick inspection, first page OCR, metadata, or overview notes.",
    )
    args = parser.parse_args()

    result = classify(args.user_request, args.input_summary, args.inputs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
