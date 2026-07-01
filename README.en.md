# yixueAIganhuo-PPT

[中文](README.md) | English

Automatically turn medical papers, PDFs, figures, screenshots, and reference materials into medical academic PowerPoint decks.
By default, the skill delivers both an **image-only PPTX** and an **object-level editable PPTX**, with Chinese speaker notes written for every slide.

![yixueAIganhuo-PPT workflow](docs/workflow-overview.webp)

## What This Project Does

`yixueAIganhuo-PPT` is a Codex skill for automated medical PowerPoint creation. It separates medical source understanding, slide visual generation, and editable PPT reconstruction into three stages:

1. **Parent agent orchestration for upstream planning**: reads papers, PDFs, figures, and screenshots, then completes medical understanding, figure inventory, PPT structure planning, and per-slide speaker notes.
2. **Middle-stage GPT Image 2 image-only slide generation**: generates medical academic slide images page by page with a consistent visual style, then assembles an image-only PPTX.
3. **Downstream page-worker editable reconstruction**: decomposes each slide image into text, image assets, lines, cards, tables, axes, and native PowerPoint shapes, then generates an editable PPTX.

The default final deliverables are:

- `editable PPTX`: object-level editable deck. Text can be revised, and images, cards, lines, and chart elements can be adjusted.
- `image-only PPTX`: full-slide raster version, suitable for sharing, archiving, and fallback presentation.
- `speaker notes`: Chinese presentation notes are generated for every slide by default. No extra option is required.

## Output Preview: Image-Only PPTX vs Editable PPTX

The left side shows the image-only PPTX, and the right side shows the editable PPTX. In the right-side screenshots, PowerPoint selection outlines reveal editable text boxes, image boxes, and shape boundaries.

![slide01 editable comparison](docs/editable-comparison-slide01.webp)

![slide05 editable comparison](docs/editable-comparison-slide05.webp)

![slide18 editable comparison](docs/editable-comparison-slide18.webp)

![slide22 editable comparison](docs/editable-comparison-slide22.webp)

## 19 Optional Styles

Before generation, you can choose one of styles 001-019. If no style is selected, the default is `001 general medical presentation PPT style`.

![19 styles template overview](docs/style-selector-19-template-overview.webp)

## Suitable Use Cases

- Medical literature reading presentations
- SCI paper journal club presentations
- Department teaching decks
- Case discussions and focused study sessions
- Guideline, review, and consensus document summaries
- Figure-heavy medical research presentations

## Requirements

### 1. Codex

This project is used as a Codex skill and needs to run in a Codex environment. **GPT Pro** is recommended for the complete workflow.

Plus users can also use it, but the token budget may be better suited to **image-only PPTX generation**. Running the full chain, including upstream medical planning, GPT Image 2 page-by-page generation, and downstream page-worker editable reconstruction, may hit token or task-length limits.

### 2. PaddleOCR-VL API Token

Downstream editable reconstruction needs accurate text recognition from slide pages, so preparing a PaddleOCR-VL token in advance is recommended.
You can obtain one from https://aistudio.baidu.com/account/accessToken. PaddleOCR-VL currently provides a free daily quota of 20,000 processed images.

## Installation

### Manual Installation

Place this repository in the Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/snowmanzhuang/yixueAIganhuo-PPT.git ~/.codex/skills/yixueAIganhuo-PPT
```

Then enter the repository and install dependencies:

```bash
cd ~/.codex/skills/yixueAIganhuo-PPT
python3 -m pip install -r requirements.txt
```

If your environment uses a virtual environment or `uv`, install the dependencies according to your own Python environment management approach.

### Let Codex Install It For You

If you do not want to type the commands yourself, you can tell Codex:

```text
Install or update https://github.com/snowmanzhuang/yixueAIganhuo-PPT into ~/.codex/skills/yixueAIganhuo-PPT, then enter that directory and install the Python dependencies from requirements.txt.
```

## Quick Start

Ask directly in Codex, for example:

```text
Use the yixueAIganhuo-PPT skill to turn ./paper.pdf into a 12-slide Chinese medical presentation PPT.
```

You can also provide a figure folder, screenshots, or other reference materials:

```text
Use the yixueAIganhuo-PPT skill to generate a 15-slide Chinese lab meeting presentation based on ./paper.pdf and ./figures/, using style 009.
```

If the page count and style are not specified in advance, the skill will ask:

```text
Please answer these questions first:

1. Page count: how many PPT slides should be generated?

2. Style: open the style selector page, choose one style from 001-019, and reply with the number.
If you do not choose, the default is: 001 general prompt style.

3. OCR: no PaddleOCR-VL token was detected.
For more accurate text recognition, obtain a token here:
https://aistudio.baidu.com/account/accessToken
Then reply with the token; you can also reply "skip" to continue.
```

The page count must be confirmed. If no style is selected, `001` is used by default. Speaker notes are generated by default and do not need to be selected separately.

## Input Materials

Supported inputs include:

- Medical paper PDFs
- Guideline, review, consensus, and report PDFs
- Figure image folders
- Experiment result screenshots, table screenshots, and medical image screenshots
- Existing PPT files, image-only PPT files, or exported slide images
- User-provided target audience, presentation scenario, page count, and style number

If the input is a paper or source material, the skill runs the full authoring workflow: medical understanding, figure inventory, PPT planning, page-by-page generation, and editable reconstruction.
If the input is already a set of slide screenshots or an image-only PPT, the skill runs the direct visual conversion workflow and tries to preserve the original pages while converting them into an editable PPTX.

## Output Structure

A complete run usually creates a directory similar to this:

```text
output/yixueAIganhuo-PPT/<run_id>/
|-- plans/
|   `-- ppt_plan.json
|-- prompts/
|   `-- slideNN.txt
|-- slides/
|   `-- slideNN.png
|-- slide_results/
|   `-- slideNN.json
|-- editppt_run/
|   |-- pages/
|   |-- manifest.json
|   `-- final outputs
|-- editable.pptx
|-- image-only.pptx
`-- notes_manifest.json
```

Exact filenames may vary depending on the run directory and `editppt` output, but the final report will clearly list:

- `editable_output`
- `image_only_output`
- page count
- speaker notes status
- validation results
- warning / retry information

## Notes

- Medical content should be reviewed by the user, especially diagnoses, treatments, guideline recommendations, and statistical conclusions.
- Original evidence figures should come from papers, figures, screenshots, or trusted materials provided by the user.
- The editable PPTX is a structured reconstruction result and is not guaranteed to be 100% identical to manually polished slide layout.
- Very complex tables, dense multi-figure pages, and special charts may require local manual adjustment.
- Plus users may be better served by generating image-only PPTX first; the complete editable reconstruction workflow is recommended for GPT Pro.

## Contact

<img src="docs/yixue-ai-ganhuo-wechat-qrcode.jpg" alt="Yixue AI Ganhua WeChat QR code" width="50%">

## Acknowledgements

The page worker in this project is largely based on [image-to-editable-ppt-skill](https://github.com/ningzimu/image-to-editable-ppt-skill). Thanks to the original author for the open-source work.
