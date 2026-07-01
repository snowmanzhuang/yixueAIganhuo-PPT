# Editable PPTX Pipeline

> Deprecated: this yixue downstream pipeline is no longer an active workflow. Current editable reconstruction is owned by `yixueAIganhuo-PPT` page workers and `editppt run finalize`. See `references/deprecated-downstream-pipeline.md`.

## Core Principle

PaddleOCR v5识别出的任何文本都应完整传递给 GPT Image 2 和后续 PPTX 文本层，不由大模型主观过滤。

The editable PPTX is reconstructed as:

```text
slide
  ├─ bottom layer: GPT Image 2 clean no-text background PNG
  └─ top layer: editable text boxes from OCR items
```

## Per-Slide Steps

For each generated slide image, start these steps immediately when the image file exists. Do not wait for subjective image-quality review or other slides:

1. Run OCR and output full OCR JSON.
2. Generate OCR annotation image for manual inspection.
3. Generate all-OCR delete overlay using semi-transparent red boxes.
4. Generate binary mask with white regions for all OCR text bboxes.
5. Generate OCR text list JSON.
6. Generate clean-background prompt that lists every OCR item and coordinate.
7. Call the selected image-edit backend with original image + overlay + binary mask.
8. Save clean background PNG in `clean_backgrounds/`.
9. Build editable text layer from OCR bbox and text.
10. Record slide-level QA results.

## Clean Prompt Contract

State that the output must be the first original PPT image repaired into a color no-text background, not a mask or annotation image.

Define image roles:

```text
1. Original color PPT page.
2. Red all-OCR delete overlay.
3. Black/white binary mask where white means OCR text region to remove.
```

Instruct removal of every OCR text item, including panel letters, one-character labels, footer text, page number, logo text, and symbols.

## OCR Inclusion Rule

Include an OCR item if:

```python
bool(text.strip()) and score >= 0.01 and bbox_width > 1 and bbox_height > 1
```

Do not exclude text because it appears to be a figure label, page number, citation, or logo. Filter only when the user explicitly asks for a specialized reconstruction policy.

## PPTX Text Reconstruction

Use 16:9 coordinate conversion:

```python
left = x1 / IMG_W * SLIDE_W_IN
top = y1 / IMG_H * SLIDE_H_IN
width = (x2 - x1) / IMG_W * SLIDE_W_IN
height = (y2 - y1) / IMG_H * SLIDE_H_IN
```

Default dimensions:

```python
IMG_W = 2560
IMG_H = 1440
SLIDE_W_IN = 16
SLIDE_H_IN = 9
```

## Font And Color Reconstruction

Use the OCR `poly` four-point box whenever available. Estimate line height from the average left and right polygon edge heights; use bbox height only as a fallback. Convert pixels to points for a 2560x1440, 16x9 inch slide, then shrink the result if the measured text width would exceed the OCR box. Do not use a fixed global multiplier such as `FONT_SCALE = 1.87`.

Pass the original first-pass slide directory to editable PPTX assembly:

```bash
python3 scripts/build_editable_pptx.py \
  --mode editable \
  --ocr-dir /path/to/ocr \
  --clean-dir /path/to/clean_backgrounds \
  --text-items-dir /path/to/clean_inputs \
  --image-dir /path/to/slides \
  --out /path/to/pptx/editable.pptx
```

When `--image-dir` is provided, sample text color from the pixel difference between the original slide image and the clean background inside each OCR bbox. Use the position/role color defaults only as fallback when sampling fails.

Merge adjacent OCR fragments for same-line headers or titles before creating PowerPoint text boxes. This reduces false line breaks when PaddleOCR splits a visually single title into multiple OCR items.

## Clean Background QA

Check that:

- output is color PPT background, not overlay or mask
- output path is under `clean_backgrounds/`, not a provider cache directory
- OCR text is removed
- non-text scientific figures and structures are preserved
- no red overlay boxes remain
- no binary mask artifacts remain
- medical evidence figures are not distorted beyond acceptable limits

Optionally rerun OCR on clean backgrounds and compare residual text against the original OCR list.
