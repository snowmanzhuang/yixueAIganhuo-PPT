#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from PIL import Image, ImageOps


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def parse_size(raw: str) -> tuple[int, int]:
    try:
        width, height = raw.lower().split("x", 1)
        return int(width), int(height)
    except ValueError as exc:
        raise SystemExit(f"Invalid --target-size value: {raw}. Expected WIDTHxHEIGHT.") from exc


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def generated_root(args: argparse.Namespace) -> Path:
    if args.generated_root:
        return Path(args.generated_root).expanduser().resolve()
    return (codex_home() / "generated_images").resolve()


def find_source_image(args: argparse.Namespace) -> Path:
    if args.source:
        source = Path(args.source).expanduser().resolve()
        if not source.exists():
            raise SystemExit(f"Source image not found: {source}")
        return source
    if not args.agent_id:
        raise SystemExit("Provide --agent-id or --source.")
    agent_dir = generated_root(args) / args.agent_id
    if not agent_dir.exists():
        raise SystemExit(f"Codex generated-image directory not found: {agent_dir}")
    candidates = [p for p in agent_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    if not candidates:
        raise SystemExit(f"No generated images found in {agent_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime).resolve()


def default_final_path(task_dir: Path, slide_id: str, role: str) -> Path:
    if role == "slide":
        return task_dir / "slides" / f"{slide_id}.png"
    if role == "clean":
        return task_dir / "clean_backgrounds" / f"{slide_id}_clean_background.png"
    raise SystemExit(f"Unsupported role: {role}")


def archive_raw(source: Path, task_dir: Path, slide_id: str, role: str, agent_id: str | None) -> Path:
    archive_dir = task_dir / "logs" / "codex_imagegen_raw"
    archive_dir.mkdir(parents=True, exist_ok=True)
    agent_part = f"_agent-{agent_id}" if agent_id else ""
    archive = archive_dir / f"{slide_id}_{role}{agent_part}{source.suffix.lower()}"
    if source.resolve() != archive.resolve():
        shutil.copy2(source, archive)
    return archive


def parse_background(raw: str) -> tuple[int, int, int]:
    value = raw.strip().lstrip("#")
    if len(value) != 6:
        raise SystemExit("--background must be a 6-digit hex color, for example #ffffff.")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def standardize_image(source: Path, out: Path, target_size: tuple[int, int], method: str, background: str) -> tuple[int, int]:
    width, height = target_size
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        source_size = image.size
        if method == "proportional_resize_center_crop":
            scale = max(width / image.width, height / image.height)
            resized_size = (round(image.width * scale), round(image.height * scale))
            resized = image.resize(resized_size, Image.Resampling.LANCZOS)
            left = max((resized.width - width) // 2, 0)
            top = max((resized.height - height) // 2, 0)
            final = resized.crop((left, top, left + width, top + height))
        elif method == "proportional_resize_letterbox":
            scale = min(width / image.width, height / image.height)
            resized_size = (round(image.width * scale), round(image.height * scale))
            resized = image.resize(resized_size, Image.Resampling.LANCZOS)
            final = Image.new("RGB", (width, height), parse_background(background))
            left = (width - resized.width) // 2
            top = (height - resized.height) // 2
            final.paste(resized, (left, top))
        else:
            raise SystemExit(f"Unsupported standardization method: {method}")
        final.save(out, format="PNG")
    return source_size


def rel(path: Path, task_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(task_dir.resolve()))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a Codex image_gen output, archive the raw image, and standardize it into the task directory.")
    parser.add_argument("--agent-id", help="Subagent id whose generated image should be collected.")
    parser.add_argument("--source", help="Optional direct source image path, mainly for validation or manual recovery.")
    parser.add_argument("--generated-root", help="Override Codex generated_images root. Defaults to ${CODEX_HOME}/generated_images.")
    parser.add_argument("--task-dir", required=True, help="Isolated task directory for this PPT workflow.")
    parser.add_argument("--slide-id", required=True, help="Slide id such as slide01.")
    parser.add_argument("--role", choices=["slide", "clean"], required=True, help="Final artifact role.")
    parser.add_argument("--out", help="Optional explicit final output path. Defaults to task_dir/slides or task_dir/clean_backgrounds.")
    parser.add_argument("--target-size", default="2560x1440", help="Final output size, default: 2560x1440.")
    parser.add_argument("--method", choices=["proportional_resize_center_crop", "proportional_resize_letterbox"], default="proportional_resize_center_crop")
    parser.add_argument("--background", default="#ffffff", help="Letterbox background color, default: #ffffff.")
    args = parser.parse_args()

    task_dir = Path(args.task_dir).expanduser().resolve()
    task_dir.mkdir(parents=True, exist_ok=True)
    source = find_source_image(args)
    final_path = Path(args.out).expanduser().resolve() if args.out else default_final_path(task_dir, args.slide_id, args.role).resolve()
    target_size = parse_size(args.target_size)
    raw_archive = archive_raw(source, task_dir, args.slide_id, args.role, args.agent_id)
    source_size = standardize_image(source, final_path, target_size, args.method, args.background)

    record = {
        "agent_id": args.agent_id,
        "raw_cache_path": str(source),
        "raw_archived_path": rel(raw_archive, task_dir),
        "final_path": rel(final_path, task_dir),
        "source_size": list(source_size),
        "target_size": list(target_size),
        "standardized": list(source_size) != list(target_size),
        "standardization_method": args.method,
    }
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
