#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
STYLE_DIR = SKILL_ROOT / 'references'
DEFAULT_STYLE_JSON = STYLE_DIR / '001_通用医学汇报PPT风格提示词.json'
STYLE_FILE_RE = re.compile(r'^(?P<index>\d{3})_(?P<name>.+)\.json$')

DEFAULT_GLOBAL_KEYS = ['medical_academic_slide', 'layout_geometry', 'typography_and_evidence', 'avoid_style']


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().read_text(encoding='utf-8'))


def available_style_files() -> list[Path]:
    return sorted(STYLE_DIR.glob('[0-9][0-9][0-9]_*.json'))


def style_display(path: Path) -> str:
    match = STYLE_FILE_RE.match(path.name)
    if not match:
        return path.stem
    return f"{match.group('index')} {match.group('name')}"


def format_style_options(paths: list[Path]) -> str:
    if not paths:
        return f'No numbered style JSON files found in {STYLE_DIR}'
    return '\n'.join(f'- {style_display(path)} ({path})' for path in paths)


def resolve_style_json(selector: str | None) -> Path:
    if not selector:
        return DEFAULT_STYLE_JSON

    raw = str(selector).strip()
    if not raw:
        return DEFAULT_STYLE_JSON

    path_like = Path(raw).expanduser()
    path_candidates = [path_like]
    if not path_like.is_absolute():
        path_candidates.append(STYLE_DIR / raw)
    for candidate in path_candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    if path_like.name == '通用医学汇报PPT风格提示词.json':
        return DEFAULT_STYLE_JSON.resolve()

    styles = available_style_files()
    if raw.isdigit():
        wanted = raw.zfill(3)
        matches = [path for path in styles if path.name.startswith(f'{wanted}_')]
    else:
        wanted = raw.casefold()
        exact = [
            path for path in styles
            if path.name.casefold() == wanted or path.stem.casefold() == wanted
        ]
        matches = exact or [
            path for path in styles
            if wanted in path.name.casefold() or wanted in path.stem.casefold()
        ]

    if len(matches) == 1:
        return matches[0].resolve()
    if len(matches) > 1:
        raise SystemExit(
            f'Ambiguous style selector: {selector}\n'
            f'Matches:\n{format_style_options(matches)}'
        )
    raise SystemExit(
        f'Style selector not found: {selector}\n'
        f'Available styles:\n{format_style_options(styles)}'
    )


def find_slide(plan: dict[str, Any], slide_id: str) -> dict[str, Any]:
    for slide in plan.get('slides', []):
        if slide.get('slide_id') == slide_id:
            return slide
    raise SystemExit(f'Slide not found in plan: {slide_id}')


def normalize_generation_keys(raw: Any, slide_number: int, slide: dict[str, Any]) -> dict[str, list[str]]:
    if isinstance(raw, dict):
        keys = {str(k): list(v or []) for k, v in raw.items()}
    else:
        keys = {'global': DEFAULT_GLOBAL_KEYS, 'continuity': [], 'illustration': [], 'asset_embedding': [], 'closing': [], 'negative_constraints': []}
        if slide_number == 1:
            keys['asset_embedding'].append('cover_no_asset')
        elif slide_number == 2:
            keys['continuity'].append('slide2_inherit_slide1')
        else:
            keys['continuity'].append('slide3_plus_inherit_slide1_slide2')
        if slide.get('asset_binding') or slide.get('assets', {}).get('required'):
            keys['asset_embedding'].append('preserve_original_asset')
        if slide.get('scientific_illustration_needed') or slide.get('content', {}).get('scientific_illustration_needed'):
            keys['illustration'].append('embedded_scientific_illustration')
        keys['negative_constraints'].append('avoid_fake_metadata')
    keys.setdefault('global', DEFAULT_GLOBAL_KEYS)
    keys.setdefault('continuity', [])
    keys.setdefault('illustration', [])
    keys.setdefault('asset_embedding', [])
    keys.setdefault('closing', [])
    keys.setdefault('negative_constraints', [])
    return keys


def style_text(style: dict[str, Any], group: str, keys: list[str]) -> list[str]:
    section = style.get(group, {})
    blocks = []
    for key in keys:
        if key not in section:
            raise SystemExit(f'Style key not found: {group}.{key}')
        blocks.append(f'[{group}.{key}]\n{section[key]}')
    return blocks


def compact_slide_json(slide: dict[str, Any]) -> str:
    return json.dumps(slide, ensure_ascii=False, indent=2)


def build_prompt(plan: dict[str, Any], style: dict[str, Any], slide: dict[str, Any], slide_number: int) -> str:
    keys = normalize_generation_keys(slide.get('generation_keys'), slide_number, slide)
    blocks: list[str] = []
    blocks.append('你正在为 GPT Image 2 生成一张医学学术 PowerPoint 页面。请严格按照以下风格键、页面计划和证据约束生成单页 16:9 PPT 图像。')
    blocks.append('不要生成网页、海报、信息流长图、UI mockup 或带浏览器/软件边框的图。输出必须是一张完整 PPT 页面。')
    blocks.append('')
    blocks.append('## 1. 已选风格提示词（必须逐条遵守）')
    for group in ['global', 'continuity', 'illustration', 'asset_embedding', 'closing', 'negative_constraints']:
        selected = keys.get(group, [])
        if selected:
            blocks.extend(style_text(style, group, selected))
    blocks.append('')
    blocks.append('## 2. 本页 PPT 计划（必须按此执行）')
    blocks.append(compact_slide_json(slide))
    deck = plan.get('deck') or {k: v for k, v in plan.items() if k not in {'slides', 'figures'}}
    if deck:
        blocks.append('')
        blocks.append('## 3. 整套汇报上下文')
        blocks.append(json.dumps(deck, ensure_ascii=False, indent=2))
    blocks.append('')
    blocks.append('## 4. 页面生成硬性要求')
    blocks.append('- 画布为 16:9 横版 PowerPoint 页面；所有元素位于安全边距内。')
    blocks.append('- 标题、模块标题、证据图、流程图、注释和底部引用必须网格对齐。')
    blocks.append('- 中文为主要汇报语言；英文只用于必要术语、图中短标签或文献。')
    blocks.append('- 不要虚构作者、医院、大学、日期、样本量、P 值、统计结果或参考文献。')
    blocks.append('- 如果本页提供原始 Figure/医学影像/论文图，请把它作为真实证据嵌入，不要重画，不要改变医学内容，不要改变宽高比。')
    blocks.append('- 如果没有原始 Figure，可生成科研示意图或机制图，但必须科学准确、克制、像医学学术汇报页面。')
    blocks.append('- 底部引用区低调显示真实来源；不要让引用栏占据主体证据区。')
    blocks.append('')
    blocks.append('## 5. 连续性规则')
    if slide_number == 1:
        blocks.append('本页是整套 PPT 的视觉母版：请建立清晰、正式、可连续复用的医学学术模板。')
    elif slide_number == 2:
        blocks.append('本页必须参考随 prompt 提供的 slide01 图片，继承母版结构，仅替换内容。')
    else:
        blocks.append('本页必须同时参考随 prompt 提供的 slide01 和 slide02 图片，不得发明新模板。')
    return '\n\n'.join(blocks).strip() + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a detailed GPT Image 2 slide prompt from ppt_plan.json and selected style JSON keys.')
    parser.add_argument('style_selector', nargs='?', help='Optional style selector: 001, 1, filename, name fragment, or JSON path. Defaults to 001.')
    parser.add_argument('--style', dest='style_option', help='Optional style selector. Takes precedence over positional style_selector.')
    parser.add_argument('--style-json', help='Backward-compatible style JSON path or selector. Takes precedence over --style and positional style_selector.')
    parser.add_argument('--list-styles', action='store_true', help='List available numbered style JSON files and exit.')
    parser.add_argument('--plan', help='Path to ppt_plan.json')
    parser.add_argument('--slide-id')
    parser.add_argument('--slide-number', type=int)
    parser.add_argument('--out')
    args = parser.parse_args()

    if args.list_styles:
        print(format_style_options(available_style_files()))
        return

    missing = [
        name for name in ['plan', 'slide_id', 'slide_number', 'out']
        if getattr(args, name) in (None, '')
    ]
    if missing:
        parser.error('missing required arguments: ' + ', '.join(f'--{name.replace("_", "-")}' for name in missing))

    style_selector = args.style_json or args.style_option or args.style_selector
    style_json = resolve_style_json(style_selector)
    plan = load_json(Path(args.plan))
    style = load_json(style_json)
    slide = find_slide(plan, args.slide_id)
    prompt = build_prompt(plan, style, slide, args.slide_number)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt, encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
