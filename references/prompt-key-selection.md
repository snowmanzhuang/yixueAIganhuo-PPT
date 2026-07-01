# Prompt Key Selection

Use the numbered style prompt JSON files under `references/` as the style prompt source. The default style is `references/001_通用医学汇报PPT风格提示词.json`.

Do not send the entire JSON file to GPT Image 2. Select only the keys needed for the current slide, but always expand the selected keys into their full text before calling GPT Image 2. Do not replace the selected style keys with a short summary such as "medical academic style".

## Default Key Groups

For most slides, include:

```text
global.medical_academic_slide
global.layout_geometry
global.typography_and_evidence
global.avoid_style
```

For slide 1, use only the current slide plan plus relevant global/style keys. Usually avoid user-uploaded figures on the cover unless explicitly requested.

For slide 2, add:

```text
continuity.slide2_inherit_slide1
```

Also provide slide 1 image as a visual reference.

For slide 3 and later, add:

```text
continuity.slide3_plus_inherit_slide1_slide2
```

Also provide slide 1 and slide 2 images as visual references.

For slides embedding original assets, add:

```text
asset_embedding.preserve_original_asset
```

Include this instruction in the prompt:

```text
请将随本 prompt 提供的原始图片作为真实医学证据嵌入本页对应区域，不要重画、不要替换为相似伪图、不要改变其医学内容。必须严格保持原始图片的宽高比例，不要拉伸、压扁、变形，也不要为了填满版面而裁切成不同宽高比；如版面区域比例不一致，请等比例缩放后用留白、细框或内边距适配。
```

For cover slides without assets, add:

```text
asset_embedding.cover_no_asset
```

For generated scientific illustrations, add:

```text
illustration.scientific_illustration_style
illustration.embedded_scientific_illustration
```

For closing slides, add:

```text
closing.acknowledgement_slide
```

For metadata-sensitive slides, add:

```text
negative_constraints.avoid_fake_metadata
```

## Per-Slide Prompt Inputs

Each page generation prompt should include:

1. Full text of the selected style prompt keys, not just key names.
2. Slide-specific plan from `ppt_plan.json`.
3. Asset binding instructions and actual image inputs when required.
4. Continuity references according to slide number.
5. Negative constraints against fake authors, institutions, dates, citations, and invented data.

Use `scripts/01_build_slide_prompt_v20260504.py` to build first-pass slide prompts whenever possible. The script accepts an optional style selector before or after the named arguments:

```bash
python3 scripts/01_build_slide_prompt_v20260504.py \
  001 \
  --plan /path/to/plans/ppt_plan.json \
  --slide-id slide01 \
  --slide-number 1 \
  --out /path/to/prompts/slide01_prompt.txt
```

Style selectors can be a number such as `1`, `001`, `009`, a full filename, a filename/name fragment such as `冷蓝斜切`, or a direct JSON path. `--style-json` is still supported for backward-compatible explicit paths. Use `--list-styles` to inspect available styles.

This script loads the selected style JSON, selects the keys in `generation_keys`, expands their full Chinese instructions, and appends the slide plan and hard constraints. If the plan lacks structured `generation_keys`, the script infers defaults by slide number and asset usage. Do not hand-write a short replacement prompt unless the user explicitly asks for a lightweight test.

Before dispatching any 页面生成 worker, validate the prompt:

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-prompt.py \
  --prompt <task>/prompts/slideNN.txt \
  --slide-number <N>
```

If validation fails, fix the prompt or upstream plan. Do not generate from a summary-style prompt and do not substitute artifact-tool, python-pptx, HTML/SVG composition, or native PPTX generation.

## Asset Use Rules

Treat original figures as evidence, not decoration. Bind each major original figure to one slide unless there is a clear reason to reuse it. Do not fill every slide with original figures mechanically. Preserve each embedded asset's original aspect ratio exactly in the first-pass GPT Image 2 slide image; never stretch, squeeze, deform, or crop it into a different ratio. If the target region has a different shape, fit proportionally and use padding, a framed evidence box, or whitespace.

If the backend cannot accept image inputs, do not pretend that an original figure was embedded. Stop and ask for a compatible backend or a revised workflow.
