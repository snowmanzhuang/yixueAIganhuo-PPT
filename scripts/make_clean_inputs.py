#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

PROMPT_TEMPLATE = """这是图像编辑任务。最终输出必须是第一张原始 PPT 的彩色修复版，不是 mask 图，不是标注图。

输入图像角色：
1. 第一张：原始彩色 PPT 页面，作为最终图的保真基础。
2. 第二张：PaddleOCR v5 全量文字标注图，红色区域和编号显示所有 PaddleOCR 识别到的文字位置。
3. 第三张：黑白删除 mask，只是编辑指令；白色区域=所有 PaddleOCR 识别到的文字区域，黑色区域=保持原图。

请清理 PaddleOCR v5 识别出的全部文字，不要由你自行判断哪些文字应该保留。凡是出现在下面清单里的文本，都需要从图像中删除并补成背景。

PaddleOCR v5 全量识别文字清单如下：
{ocr_text_list}

严格执行：
- 删除清单中每一项文字，以及这些文字的数字、字母、符号、单位、残影和笔画。
- 包括图内面板字母、单字符、边缘小字、底部小字；只要在清单中就删除。
- 第三张黑白 mask 的白色区域内不能留下任何清单文字或残留字形。
- 删除后用原位置周围背景自然修复，尽量保留非文字图形结构、线条、底色、图表、卡片框、表格线和页面结构。
- 黑色 mask 区域尽量保持第一张原图不变。

失败条件：输出图中还能看到清单中的任意文字、数字、字母、单位或残影。成功条件：输出是彩色 PPT 页面，PaddleOCR 清单文字全部消失，其他非文字结构尽量保持原样。
"""


def include_all_ocr_text(item: dict) -> bool:
    text = item["text"].strip()
    score = float(item["score"])
    x1, y1, x2, y2 = item["bbox"]
    return bool(text) and score >= 0.01 and x2 - x1 > 1 and y2 - y1 > 1


def format_ocr_text_list(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        x1, y1, x2, y2 = [int(round(v)) for v in item["bbox"]]
        text = item["text"].strip().replace("`", "'")
        lines.append(f"{i}. `{text}`，位置约 x={x1}-{x2}, y={y1}-{y2}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create overlay, binary mask, OCR text list, and clean prompt for one slide.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--ocr-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prompt-dir", required=True)
    parser.add_argument("--slide-id", required=True)
    args = parser.parse_args()

    image_path = Path(args.image)
    out_dir = Path(args.out_dir)
    prompt_dir = Path(args.prompt_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)

    source = Image.open(image_path).convert("RGB")
    items = json.loads(Path(args.ocr_json).read_text(encoding="utf-8"))
    included = [item for item in items if include_all_ocr_text(item)]

    overlay = source.copy().convert("RGBA")
    mark = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(mark)
    for i, item in enumerate(included, 1):
        x1, y1, x2, y2 = [int(round(v)) for v in item["bbox"]]
        draw.rectangle([x1 - 4, y1 - 3, x2 + 4, y2 + 3], fill=(255, 0, 0, 125), outline=(255, 0, 0, 255), width=3)
        draw.text((x1, max(0, y1 - 16)), str(i), fill=(255, 0, 0, 255))
    overlay_path = out_dir / f"{args.slide_id}_all_ocr_delete_overlay.png"
    Image.alpha_composite(overlay, mark).convert("RGB").save(overlay_path)

    binary = Image.new("RGB", source.size, "black")
    draw = ImageDraw.Draw(binary)
    for item in included:
        x1, y1, x2, y2 = [int(round(v)) for v in item["bbox"]]
        draw.rectangle([x1 - 4, y1 - 3, x2 + 4, y2 + 3], fill="white")
    binary_path = out_dir / f"{args.slide_id}_all_ocr_delete_binary_mask.png"
    binary.save(binary_path)

    text_items_path = out_dir / f"{args.slide_id}_all_ocr_text_items.json"
    text_items_path.write_text(json.dumps(included, ensure_ascii=False, indent=2), encoding="utf-8")

    prompt_path = prompt_dir / f"{args.slide_id}_clean_prompt.txt"
    prompt_path.write_text(PROMPT_TEMPLATE.format(ocr_text_list=format_ocr_text_list(included)), encoding="utf-8")

    print(json.dumps({"slide_id": args.slide_id, "overlay": str(overlay_path), "binary_mask": str(binary_path), "text_items": str(text_items_path), "prompt": str(prompt_path), "items": len(included)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
