#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _input_normalization import copy_input, save_image_page
from deck_run_state import (
    load_deck,
    load_jobs,
    now_iso,
    rel_to_run,
    run_dir_from_target,
    save_deck,
    save_jobs,
    set_run_status,
    write_json,
)
from prepare_deck_run import page_request


def next_page_index(deck: dict) -> int:
    indexes = [int(page.get("page_index", 0)) for page in deck.get("pages", [])]
    return max(indexes, default=0) + 1


def build_deck_page(run_dir: Path, page_index: int, source: Path, copied_input: Path, source_page: int) -> dict:
    rel_page_dir = source.parent.relative_to(run_dir).as_posix()
    return {
        "page_index": page_index,
        "source_page": source_page,
        "source_image": source.relative_to(run_dir).as_posix(),
        "page_dir": rel_page_dir,
        "manifest": f"{rel_page_dir}/manifest.json",
        "validation": f"{rel_page_dir}/validation.json",
        "input": copied_input.name,
        "agent_status": "pending",
        "page_id": f"page_{page_index:03d}",
        "status": "pending",
        "page_request": f"{rel_page_dir}/page_request.json",
        "dispatch": None,
        "result": None,
        "accepted": False,
    }


def append_page(run_dir: Path, image: Path, source_page: int) -> dict:
    deck = load_deck(run_dir)
    jobs = load_jobs(run_dir)
    page_index = next_page_index(deck)
    page_id = f"page_{page_index:03d}"
    page_dir = run_dir / "pages" / page_id

    copied = copy_input(image, run_dir / "input")
    source = save_image_page(copied, page_dir)
    deck_page = build_deck_page(run_dir, page_index, source, copied, source_page)
    deck.setdefault("pages", []).append(deck_page)
    deck["page_count"] = len(deck["pages"])
    if deck.get("input_type") == "image":
        deck["input_type"] = "images"
    deck.setdefault("inputs", []).append(copied.relative_to(run_dir).as_posix())
    deck["updated_at"] = now_iso()

    request = page_request(run_dir, deck, deck_page)
    if deck.get("image_backend"):
        request["image_backend"] = deck["image_backend"]
    write_json(page_dir / "page_request.json", request)
    write_json(
        page_dir / "imagegen-jobs.json",
        {"schema_version": 1, "run_id": deck["run_id"], "page_id": page_id, "jobs": []},
    )

    jobs.setdefault("pages", []).append(
        {
            "page_id": page_id,
            "page_index": page_index,
            "status": "pending",
            "page_dir": deck_page["page_dir"],
            "source": deck_page["source_image"],
            "page_request": rel_to_run(run_dir, page_dir / "page_request.json"),
            "manifest": deck_page["manifest"],
            "validation": deck_page["validation"],
            "dispatch": None,
            "result": None,
            "accepted": False,
        }
    )
    jobs["updated_at"] = now_iso()
    if jobs.get("run_status") in {"pages_dispatched", "pages_recorded", "complete"}:
        jobs["run_status"] = "inputs_prepared"

    save_deck(run_dir, deck)
    save_jobs(run_dir, jobs)
    set_run_status(run_dir, "inputs_prepared", f"added {page_id}")
    return {
        "run_dir": str(run_dir),
        "page_id": page_id,
        "page_index": page_index,
        "source": deck_page["source_image"],
        "page_request": deck_page["page_request"],
        "status": "pending",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Append one generated slide image to an existing editppt run.")
    parser.add_argument("run", help="Run directory or deck_manifest.json")
    parser.add_argument("image", help="Generated slide image to append")
    parser.add_argument("--source-page", type=int, help="Original/generated slide number. Defaults to next page index.")
    args = parser.parse_args()

    run_dir = run_dir_from_target(args.run)
    image = Path(args.image).expanduser().resolve()
    if not image.exists():
        raise SystemExit(f"Image not found: {image}")
    deck = load_deck(run_dir)
    source_page = args.source_page or next_page_index(deck)
    result = append_page(run_dir, image, source_page)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
