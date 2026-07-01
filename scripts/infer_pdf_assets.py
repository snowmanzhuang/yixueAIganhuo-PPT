#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def infer_figure_mentions(text: str) -> list[str]:
    patterns = [
        r"\b(?:Fig(?:ure)?\.?)\s*([A-Za-z]?\d+)[A-Za-z]?",
        r"\bExtended Data Fig\.??\s*(\d+)[A-Za-z]?",
        r"\bSupplementary Fig\.??\s*(\d+)[A-Za-z]?",
        r"图\s*(\d+)[A-Za-z]?",
    ]
    mentions = []
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            mentions.append(str(match).strip())
    return sorted(set(mentions), key=lambda value: int(re.search(r"\d+", value).group()))


def main_figure_numbers(mentions: list[str]) -> list[int]:
    numbers = []
    for mention in mentions:
        match = re.search(r"\d+", mention)
        if match:
            numbers.append(int(match.group()))
    return sorted(set(numbers))


def continuous_expected_count(numbers: list[int]) -> int:
    expected = 0
    for number in sorted(numbers):
        if number == expected + 1:
            expected = number
        elif number > expected + 1:
            break
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer figure mentions from extracted PDF text. Pair with project extract_article_figures.py for image extraction.")
    parser.add_argument("--text", required=True, help="Plain text extracted from PDF")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    text_path = Path(args.text)
    text = text_path.read_text(encoding="utf-8", errors="ignore")
    mentions = infer_figure_mentions(text)
    numbers = main_figure_numbers(mentions)
    expected_count = continuous_expected_count(numbers)
    out = {
        "source_text": str(text_path),
        "inferred_main_figure_mentions": mentions,
        "inferred_main_figure_numbers": numbers,
        "expected_main_figure_count": expected_count,
        "note": "Use expected_main_figure_count as the pre-question estimate, then compare with extracted image candidates and discard logos/decorations/non-figure images."
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
