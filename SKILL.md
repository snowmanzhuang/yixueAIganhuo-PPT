---
name: yixueAIganhuo-PPT
description: Use when creating a complete editable medical academic PowerPoint deck from papers, PDFs, Figures, screenshots, or support documents, or when converting an existing visual slide deck/image PDF into editable PPTX. Handles task routing, medical source understanding, Figure inventory, PPT planning, GPT Image 2 slide generation through editppt image, page-worker reconstruction, and final PPTX assembly.
---

# yixueAIganhuo-PPT

`yixueAIganhuo-PPT` is now the 唯一完整 skill for the end-to-end workflow:

```text
medical sources
  -> 医学上游 worker
  -> ppt_plan.json and slide prompts
  -> 页面生成 worker via editppt image
  -> page worker editable reconstruction
  -> editppt run finalize
  -> final editable PPTX
```

The 统一父 agent in this skill is a scheduler. It creates the task directory, maintains global state, dispatches workers, controls concurrency, collects structured results, and runs deterministic `editppt` commands. It does not personally absorb full PDF text, every Figure detail, every prompt, OCR details, or page-level `manifest.json` decisions into its context.

Parent context budget: keep the parent thread limited to routing decisions, worker dispatch, state paths, validation summaries, and final reporting. Do not perform medical PPT planning in the parent thread. The parent must dispatch the 医学上游 worker before reading full source text and must keep structured artifacts only in its own context.

Do not ask the user to approve sub-agent spawning. Once the skill is chosen and prerequisites are satisfied, sub-agent dispatch is part of the workflow. Do not ask for a reply such as a permission phrase; proceed with worker dispatch and report progress.

## References

- `references/single-skill-prd.md`: product and architecture baseline for the merged single-skill workflow.
- `references/workflow-overview.md`: upstream medical planning DAG.
- `references/prompt-key-selection.md`: style key selection and per-slide prompt construction.
- `references/style_selector/`: local HTML style selector page and 001-019 template/example preview assets.
- `references/provider-config.md`: unified `editppt image` backend contract.
- `references/medical-integrated-workflow.md`: parent orchestration, worker boundaries, concurrency, incremental page intake, and failure handling.
- `references/cli-helper.md`: `editppt` install check and command manual.
- `references/page-decision-tree.md`: page-worker object-source decisions.
- `references/manifest-schema.md`: `editppt` run/page JSON contracts.
- `scripts/start-style-selector.py`: launches the local style selector page from the skill bundle.
- `scripts/classify-task-route.py`: lightweight helper for initial task-route classification.
- `scripts/validate-slide-prompt.py`: full-authoring rich GPT Image 2 prompt gate before slide-image worker dispatch.
- `scripts/validate-slide-ready.py`: full-authoring preflight gate before downstream conversion commands.
- `prompts/medical-upstream-worker.md`: prompt template for medical planning workers.
- `prompts/medical-slide-image-worker.md`: prompt template for single-slide image generation workers.
- `prompts/page-worker.md`: prompt template for downstream editable page workers.

## Retained Capabilities

The skill keeps the original medical creation value:

- source reading and concise medical summary
- PDF/Figure inventory and evidence Figure selection
- target slide structure and narrative planning
- `ppt_plan.json`
- Chinese speaker notes
- page dependencies
- per-slide GPT Image prompt writing

The skill also embeds the downstream editable reconstruction value:

- `editppt` CLI
- page worker dispatch
- `manifest.json`
- OCR/text hints
- foreground image asset reconstruction
- PPT native element reconstruction
- page validation
- final deck assembly through `editppt run finalize`

## Deprecated Components

The old yixue text-overlay editable path is deprecated. Do not use legacy OCR/image-repair PPTX scripts as the current execution path. The authoritative editable path is now the embedded `editppt` page-worker workflow.

## Task Routing

Before creating downstream jobs, inspect the user request and input files, then write `task_route` into `task_state.json`.

Recommended helper:

```bash
python yixueAIganhuo-PPT/scripts/classify-task-route.py \
  --user-request "<original user request>" \
  --input-summary "<brief first-page/overview/OCR/metadata notes>" \
  <input paths...>
```

Use the helper output as structured guidance, then apply the rules below. If a PDF preview clearly shows title/authors/abstract/body/references, choose `FULL_AUTHORING_FROM_SOURCE` even when the user says "转 PPTX".

| `task_route` | Use When | Execution |
|---|---|---|
| `FULL_AUTHORING_FROM_SOURCE` | Inputs are source material for a new medical PPT: research PDF, medical paper, report, article, manuscript, guideline, support document, Figure folder, chart image, screenshot evidence, or mixed reference assets. A PDF with title/authors/abstract/body/references or journal-style columns is source material even if the user says "转 PPTX". | Default route. Run the 医学上游 worker first, create `ppt_plan.json`, generate new 16:9 slide images through `editppt image`, then send generated slide images to page workers. Do not run `editppt prepare` on a research/material PDF as the first action. |
| `DIRECT_VISUAL_CONVERSION` | The user explicitly wants an existing visual slide deck, screenshot set, exported image-only PPT, or already-designed page PDF converted to editable PPTX while preserving the current pages as-is. Clear visual signals include 16:9 slide pages, existing slide titles/layouts, or page screenshots meant to be reconstructed rather than interpreted as evidence. | Skip medical upstream authoring. Run direct visual conversion with `editppt prepare` on the visual input, then page workers and `editppt run finalize`. |
| `AMBIGUOUS_INPUT` | A PDF/image set could plausibly be either source material or an existing visual slide deck after quick inspection. | Ask one concise clarification. Suggested wording: "这份 PDF 是制作医学 PPT 的资料，还是已有幻灯片/截图需要转可编辑 PPTX？" If inspection clearly shows a medical paper/source document, do not ask; choose `FULL_AUTHORING_FROM_SOURCE`. |

Do not treat a research/material PDF as an existing visual slide deck merely because it is a PDF.

## Full Authoring Hard Gate

For `FULL_AUTHORING_FROM_SOURCE`, the final PPTX is invalid unless every slide passes the complete chain:

1. `prompts/slideNN.txt` follows the rich prompt schema from `references/prompt-key-selection.md` and passes:

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-prompt.py \
  --prompt <task>/prompts/slideNN.txt \
  --slide-number <N>
```

2. `slides/slideNN.png` is generated by `editppt image generate/edit/batch` through the 页面生成 worker.
3. `slide_results/slideNN.json` has `status: "IMAGE_READY"`, `passed: true`, and `image_backend.tool_call` showing `editppt image generate/edit/batch`.
4. `scripts/validate-slide-ready.py` passes for every generated slide before `editppt prepare` or `editppt run add-page`.
5. Every page is reconstructed by a page worker, recorded by `editppt run record`, and assembled only by `editppt run finalize`.

Do not use @oai/artifact-tool, python-pptx, HTML/SVG screenshots, local PIL composition, direct native PPT generation, legacy yixue scripts, or any presentation/PPTX authoring shortcut as a substitute final path. If workers or image backend are unavailable, stop and report the blocker; do not downgrade to a simpler PPTX path.

## Preflight Questions Gate

Before dispatching the 医学上游 worker for `FULL_AUTHORING_FROM_SOURCE`, ask a concise preflight question block unless all required values are already known.

Before showing the block, start the bundled style selector server from this skill and use the printed `点击打开：...` URL as `{style_selector_url}`. Do not automatically open the browser; present the URL in the question block so the user can click it when needed:

```bash
python3 yixueAIganhuo-PPT/scripts/start-style-selector.py --background
```

If the local server cannot start, use the printed `本地文件兜底：...` file URL instead. The launcher resolves paths relative to its own script location, so it works when the whole skill folder is copied to another computer or installed under another username.

The block must start with: "请先回答下面几个问题："

Use numbered emoji labels only:

```text
请先回答下面几个问题：

1️⃣ 页数：这次生成多少页 PPT？

2️⃣ 风格：请打开风格选择页，选 001-019 后回复序号。
{style_selector_url}
不选则默认：001 通用提示词风格。
```

If no PaddleOCR-VL token is detected, append the third question:

```text
3️⃣ OCR：未检测到 PaddleOCR-VL token。
需要更准的文字识别，请打开这里获取 token：
https://aistudio.baidu.com/account/accessToken
然后回复 token；也可以回复“跳过”继续。
```

If a PaddleOCR-VL token is already detected, do not show the OCR prompt; ask only questions 1️⃣ and 2️⃣. The OCR token question is optional and must not block generation if the user chooses to skip.

The page count remains a hard gate. Ask the user for the target slide count before dispatching the 医学上游 worker unless the request already gives an explicit count. Do not default to any page count. Do not offer preset page-count choices. Record the confirmed number in `task_state.json` as `target_slide_count_confirmed` and pass it to the upstream worker as `TARGET_SLIDE_COUNT`.

The style selector is optional. If the user gives a valid selector (`001`-`019`, a matching style name fragment, or a style JSON filename/path), record it in `task_state.json` as `style_selector` and pass it to the upstream worker as `STYLE_SELECTOR`. If the user does not choose a style, record and pass `STYLE_SELECTOR=001`.

If the user gives a range, ask for one concrete number. If the user refuses to decide, stop and ask for a numeric page count; do not silently choose a count and do not present preset options.

## Parent Workflow

1. Create one task directory, for example `output/yixueAIganhuo-PPT/<run_id>/`.
2. Classify the task with the Task Routing rules and write `task_route` to `task_state.json`.
3. If `task_route` is `DIRECT_VISUAL_CONVERSION`, follow Direct Visual Conversion Workflow below and skip the full-authoring steps 4-15.
4. Write `task_state.json` with run phase, worker ids, per-slide status, paths, retries, concurrency slots, `task_route`, `style_selector`, and optional `style_selector_url`.
5. Dispatch the 医学上游 worker using `prompts/medical-upstream-worker.md`. The parent passes `TARGET_SLIDE_COUNT` only after `target_slide_count_confirmed=true`, and passes `STYLE_SELECTOR` after the user chooses a style or the parent defaults it to `001`; it does not create the PPT outline or slide prompts itself.
6. Receive only structured upstream artifacts:
   - `source_inventory.json`
   - `figure_inventory.json`
   - `plans/ppt_plan.json`
   - `prompts/slideNN.txt`
7. Validate that `ppt_plan.json` has one entry per target slide, continuous slide numbers, speaker notes, asset bindings, prompt files, and page dependencies.
8. Validate every slide prompt before dispatching 页面生成 workers:

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-prompt.py \
  --prompt <task>/prompts/slideNN.txt \
  --slide-number <N>
```

Do not dispatch a 页面生成 worker with a summary-style prompt, a prompt that only says "medical academic style", or a prompt that lacks layout geometry, evidence/asset bindings, negative constraints, and continuity rules.

9. Configure or verify the unified image backend:

```bash
editppt setup
editppt doctor
```

Use `editppt config` only when API fallback credentials are needed.

10. Dispatch 页面生成 worker jobs:
   - slide 1 first
   - slide 2 after slide 1 exists, with slide 1 as style reference
   - slide 3+ after slide 2 exists, with slide 1 and slide 2 as style references
11. Every 页面生成 worker must call `editppt image generate/edit/batch`. It writes `slides/slideNN.png` and `slide_results/slideNN.json`.
12. Before the first generated slide enters downstream conversion, run the real slide image preflight:

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-ready.py \
  --slide <task>/slides/slide01.png \
  --result <task>/slide_results/slide01.json
```

Do not call `editppt prepare` until this preflight passes. A valid full-authoring slide requires `slides/slideNN.png`, `slide_results/slideNN.json`, `status: "IMAGE_READY"`, `passed: true`, provenance from `editppt image generate/edit/batch`, 16:9 dimensions, and nonblank image content. Forbidden inputs include blank or white placeholder PNGs, pure-color or low-variance placeholders, synthetic `slides/sources/slideNN.png` files used only to initialize `editppt_run`, and any hand-written page manifest built against placeholder `source.png`.

13. As soon as the first generated page image passes preflight, create the conversion run:

```bash
editppt prepare <task>/slides/slide01.png --job-dir <task>/editppt_run
```

14. As later slide images finish, run the same preflight for each slide before appending it:

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-ready.py \
  --slide <task>/slides/slideNN.png \
  --result <task>/slide_results/slideNN.json
```

15. Append only preflight-passed slide images:

```bash
editppt run add-page <task>/editppt_run <task>/slides/slideNN.png --source-page <N>
```

16. Use `editppt run next <task>/editppt_run --json` to drive page conversion. For each suggested page:

```bash
python yixueAIganhuo-PPT/scripts/build-page-worker-prompt.py \
  <task>/editppt_run \
  --page page_001 \
  --out <task>/editppt_run/pages/page_001/worker-prompt.md
```

Spawn a real page worker, then record the dispatch:

```bash
editppt run dispatch <task>/editppt_run \
  --page page_001 \
  --agent-id <worker-id> \
  --prompt-file <task>/editppt_run/pages/page_001/worker-prompt.md
```

After the worker returns:

```bash
editppt run record <task>/editppt_run --page page_001 --agent-id <worker-id>
```

17. When all pages are recorded:

```bash
editppt run finalize <task>/editppt_run
```

18. Report `editable_output`, `image_only_output`, validation result, page count, warnings, and retries.

## Direct Visual Conversion Workflow

Use this branch only for `DIRECT_VISUAL_CONVERSION`, where the input is an existing visual slide deck or already-designed page images/PDF that should be preserved as-is.

1. Create the conversion run directly from the visual input:

```bash
editppt prepare <visual-input> --job-dir <task>/editppt_run
```

2. Use the same page-worker loop: `editppt run next`, `scripts/build-page-worker-prompt.py`, worker dispatch, `editppt run record`.
3. When every page is recorded, run `editppt run finalize <task>/editppt_run`.
4. Report `editable_output`, `image_only_output`, validation result, page count, warnings, and retries.

## Concurrency

- The agent pool starts with one 医学上游 worker for source understanding, PPT planning, speaker notes, and prompt writing.
- After upstream artifacts are valid, dispatch multiple 页面生成 worker jobs according to slide dependencies.
- As soon as any slide image passes `scripts/validate-slide-ready.py`, dispatch a page worker for that page immediately; do not wait for every slide image to finish.
- Once any slide image exists, reduce slide-image generation concurrency to 2 or less.
- The agent pool gradually reallocates worker slots to page workers as more validated slide images arrive.
- Reserve remaining capacity for downstream page workers.
- Keep page-worker concurrency bounded by `page_jobs.json.max_concurrent_pages`.
- Never dispatch two workers for the same slide/page.
- Never retry an unchanged failed page. Read the failure file, fix root cause, then `editppt run reset` and dispatch a fresh worker.

## Worker Boundaries

### 医学上游 worker

Owns source understanding, Figure inventory, `ppt_plan.json`, speaker notes, page dependencies, and slide prompt files. It does not generate PPTX files or page-level `manifest.json`.

### 页面生成 worker

Owns exactly one generated slide image. It uses only `editppt image generate/edit/batch`, writes `slides/slideNN.png`, and returns `slide_results/slideNN.json`.

### page worker

Owns exactly one `editppt_run/pages/page_NNN/` directory. It follows `prompts/page-worker.md`, `references/page-decision-tree.md`, and `references/manifest-schema.md`, then returns page conversion result paths.

## Required Final Output

The final deliverables are both required:

- final editable PPTX: object-level editable `.pptx` created by `editppt run finalize`
- final image-only PPTX: a full-slide raster companion deck created from the generated slide images

Both outputs must carry speaker notes from `notes_manifest.json` when notes are available. The final report must include `editable_output` and `image_only_output`.
