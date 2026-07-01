#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

from deck_run_state import load_deck, load_jobs, now_iso, run_dir_from_target, save_deck, save_jobs, set_run_status, write_json
from build_pptx_from_manifest import page_entries_from_deck_manifest, write_deck


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command):
    print("+ " + " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], check=True)


def final_output_path(run_dir, deck):
    output = Path(deck.get("output", "final/deck_edited.pptx"))
    if output.is_absolute():
        return output
    return run_dir / output


def image_only_output_path(editable_path):
    editable = Path(editable_path)
    stem = editable.stem
    if stem.endswith("_edited"):
        stem = stem[: -len("_edited")]
    return editable.with_name(f"{stem}_image_only.pptx")


def assert_pages_ready(run_dir, jobs):
    problems = []
    for page in jobs.get("pages", []):
        if page.get("status") not in {"recorded", "accepted"}:
            problems.append(f"{page['page_id']} status={page.get('status')}")
            continue
        result = page.get("result") or {}
        if result.get("validation_passed") is not True:
            problems.append(f"{page['page_id']} validation_passed={result.get('validation_passed')}")
    if problems:
        raise SystemExit("Pages are not ready for finalize:\n" + "\n".join(problems))


def resolve_run_path(run_dir, value):
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (Path(run_dir) / path).resolve()


def build_image_only_page_entries(run_dir, deck):
    slide = deck.get("slide") or {"width": 13.333, "height": 7.5, "size_mode": "wide"}
    entries = []
    manifest_base = Path(run_dir) / "deck_manifest.json"
    for page in deck.get("pages", []):
        source = resolve_run_path(run_dir, page["source_image"])
        manifest = {
            "schema_version": 1,
            "slide": slide,
            "content_box": {"left": 0, "top": 0, "width": slide.get("width", 13.333), "height": slide.get("height", 7.5)},
            "source": {"path": str(source)},
            "text_inventory": [],
            "visual_inventory": [
                {
                    "id": f"{page.get('page_id', 'page')}_full_slide_image",
                    "description": "image-only full-slide source image, not editable reconstruction",
                    "role": "image-only-output",
                }
            ],
            "background_strategy": {
                "mode": "image-only-full-slide",
                "source_consistency_contract": "preserve generated slide image exactly as a full-slide raster",
                "removed_foreground": [],
                "comparison_note": "image-only companion deck intentionally uses the generated slide image as a full-slide raster",
            },
            "quality_checks": {
                "font_size_calibrated": True,
                "visual_inventory_matched": True,
                "background_strategy_checked": True,
                "shape_corner_geometry_checked": True,
            },
            "text_boxes": [],
            "shapes": [],
            "images": [
                {
                    "id": f"{page.get('page_id', 'page')}_full_slide",
                    "path": str(source),
                    "left": 0,
                    "top": 0,
                    "width": slide.get("width", 13.333),
                    "height": slide.get("height", 7.5),
                }
            ],
            "asset_provenance": [
                {
                    "path": str(source),
                    "source": str(source),
                    "source_type": "imagegen",
                    "provenance_note": "Full-slide raster used only for the required image-only companion PPTX.",
                }
            ],
        }
        entries.append({"manifest": manifest, "manifest_path": manifest_base})
    return entries


def main():
    parser = argparse.ArgumentParser(description="Build the final editable PPTX and image-only PPTX from recorded pages.")
    parser.add_argument("run", help="Run directory or deck_manifest.json")
    args = parser.parse_args()

    run_dir = run_dir_from_target(args.run)
    deck = load_deck(run_dir)
    jobs = load_jobs(run_dir)
    assert_pages_ready(run_dir, jobs)

    out = final_output_path(run_dir, deck)
    out.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, SCRIPT_DIR / "build_pptx_from_manifest.py", "--deck-manifest", run_dir / "deck_manifest.json", "--out", out])
    set_run_status(run_dir, "deck_built", "final pptx built")

    validation = out.parent / "validation.json"
    run([sys.executable, SCRIPT_DIR / "validate_pptx.py", out, "--deck-manifest", run_dir / "deck_manifest.json", "--report", validation])
    set_run_status(run_dir, "deck_validated", "final pptx validation passed")

    image_only = image_only_output_path(out)
    _deck_for_notes, _editable_entries, notes_entries = page_entries_from_deck_manifest(run_dir / "deck_manifest.json")
    write_deck(deck, build_image_only_page_entries(run_dir, deck), image_only, notes_entries)
    set_run_status(run_dir, "image_only_deck_built", "image-only companion pptx built")

    for page in jobs.get("pages", []):
        page["status"] = "accepted"
        page["accepted"] = True
        page["accepted_at"] = now_iso()
    jobs["run_status"] = "complete"
    jobs["updated_at"] = now_iso()
    save_jobs(run_dir, jobs)
    deck["completed_at"] = now_iso()
    save_deck(run_dir, deck)
    summary = {
        "schema_version": 1,
        "run_id": deck.get("run_id"),
        "status": "complete",
        "page_count": len(jobs.get("pages", [])),
        "output": str(out),
        "editable_output": str(out),
        "image_only_output": str(image_only),
        "validation": str(validation),
        "editable_validation": str(validation),
        "completed_at": now_iso(),
    }
    write_json(out.parent / "run_summary.json", summary)
    set_run_status(run_dir, "complete", "final deck complete")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
