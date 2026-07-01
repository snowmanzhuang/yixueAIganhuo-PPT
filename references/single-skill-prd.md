# yixueAIganhuo-PPT 单 Skill 统一工作流 PRD

## 背景

当前目录原本有两类能力：

- `yixueAIganhuo-PPT` 的医学 PPT 上游创作能力：资料理解、Figure 筛选、页数规划、页面结构、讲稿、页面依赖关系和生图提示词。
- `image-to-editable-ppt` 的图片转可编辑 PPTX 下游重建能力：page worker、`manifest.json`、OCR/text hints、前景图资产重建、PPT 原生元素重建、`editppt` CLI 和最终 deck finalize。

最终产品形态调整为：只调用一个 `$yixueAIganhuo-PPT` skill 即可完成完整流程。下游能力迁入 `yixueAIganhuo-PPT` 内部；`image-to-editable-ppt` 可作为历史来源保留，但不再是主入口。

## 目标

1. `yixueAIganhuo-PPT` 成为唯一完整 skill 入口。
2. `yixueAIganhuo-PPT` 内部的统一父 agent 只做调度和状态管理。
3. 医学上游 worker 保留资料理解、Figure 盘点、`ppt_plan.json`、讲稿、页面依赖和 prompt 编写能力。
4. 页面生成 worker 通过 `editppt image generate/edit/batch` 生成完整 PPT 页面图片。
5. page worker 使用迁入的下游能力，把页面图片转成可编辑 PPTX 页面。
6. 最终通过 `editppt run finalize` 同时输出 final editable PPTX 和 final image-only PPTX。
7. 父 agent 必须先做 Task Routing，区分研究素材输入和已有图像型幻灯片输入。
8. `FULL_AUTHORING_FROM_SOURCE` 必须一开始确认生成页数，不允许默认任何页数。
9. 父 agent 必须控制 parent context budget，只保留结构化状态，把医学规划、提示词写作、生图和 page worker 重建交给子 agent。

## 非目标

- 不保留 yixue 旧的 clean-background + OCR text overlay 可编辑化路径作为执行路径。
- 不让父 agent 亲自处理 PDF 全文、完整 OCR、逐页 `manifest.json` 或页面细节设计。
- 不允许本地 PIL/HTML/SVG/python-pptx 拼接完整页面图。
- 不允许页面生成 worker 绕过 `editppt image`。
- 不允许 `@oai/artifact-tool`、python-pptx、HTML/SVG composition、local PIL composition、direct native PPT generation 或其他 presentation authoring shortcut 作为 FULL_AUTHORING_FROM_SOURCE 的最终路径。

## 架构

```text
yixueAIganhuo-PPT parent agent
  ├─ 医学上游 worker
  │   ├─ source_inventory.json
  │   ├─ figure_inventory.json
  │   ├─ ppt_plan.json
  │   └─ prompts/slideNN.txt
  ├─ 页面生成 worker
  │   ├─ editppt image generate/edit/batch
  │   ├─ slides/slideNN.png
  │   └─ slide_results/slideNN.json
  └─ page worker
      ├─ manifest.json
      ├─ imagegen-jobs.json
      ├─ page.pptx
      ├─ preview.png
      ├─ validation.json
      └─ page_result.json
```

## Task Routing

父 agent 在创建 worker 前必须设置 `task_route`：

| `task_route` | 场景 | 期望行为 |
|---|---|---|
| `FULL_AUTHORING_FROM_SOURCE` | 用户提供 research/material PDF、医学论文、报告、指南、Figure、截图证据或支持文档，目标是制作新的医学 PPT。 | 默认路径。执行 full upstream medical PPT authoring，先产出 `ppt_plan.json` 和新页面图，再交给 page worker。 |
| `DIRECT_VISUAL_CONVERSION` | 用户提供 existing image-based deck、已有幻灯片截图、导出的图像型 PPT/PDF，目标是保留现有页面外观并转可编辑 PPTX。 | 跳过医学上游制作，直接对视觉输入运行 `editppt prepare`，再 page worker + finalize。 |
| `AMBIGUOUS_INPUT` | 简单检查后仍无法判断输入是素材还是已有幻灯片。 | 只问一个简短澄清问题，再选择其中一个明确路径。 |

Do not treat a source-material PDF as an already-generated deck. 研究论文 PDF、素材 PDF、医学报告 PDF 默认走 `FULL_AUTHORING_FROM_SOURCE`，不是直接 `editppt prepare`。

`scripts/classify-task-route.py` 提供轻量可执行建议，输入用户请求、快速预览摘要和文件路径，输出 `task_route`、是否允许第一步 `editppt prepare`、原因和可选澄清问题。父 agent 仍以主 `SKILL.md` 的规则做最终判断。

## Full Authoring Hard Gate

`FULL_AUTHORING_FROM_SOURCE` 下，final PPTX is invalid unless:

1. 每页 `prompts/slideNN.txt` 是 rich prompt schema 生成的 GPT Image 2 页面提示词，并通过 `scripts/validate-slide-prompt.py`。
2. 每页 `slides/slideNN.png` 由 `editppt image generate/edit/batch` 生成，而不是 `@oai/artifact-tool`、python-pptx、HTML/SVG 截图、本地 PIL 合成或 direct native PPT generation。
3. 每页 `slide_results/slideNN.json` 记录 `status: "IMAGE_READY"`、`passed: true`、`image_backend.tool_call: "editppt image generate/edit/batch"`。
4. 每页生成图进入 `editppt prepare` 或 `editppt run add-page` 前通过 `scripts/validate-slide-ready.py`。
5. 最终 PPTX 只在 page worker 重建、`editppt run record` 和 `editppt run finalize` 后交付。

Do not use @oai/artifact-tool, python-pptx, HTML/SVG composition, local PIL composition, direct native PPT generation, or legacy scripts as substitute output. If workers or image backend are unavailable, stop and report the blocker.

## Slide Count Gate

FULL_AUTHORING_FROM_SOURCE 下，父 agent 在派发医学上游 worker 前必须 Ask the user for the target slide count，除非用户请求里已经明确写了页数。固定使用开放式问题："请问这次要生成多少页 PPT？" Do not default to any page count。Do not offer preset page-count choices。父 agent 必须在 `task_state.json` 写入 `target_slide_count_confirmed` 和 `TARGET_SLIDE_COUNT`，医学上游 worker 只能基于这个确认值生成 `ppt_plan.json`。

## Parent Context Budget

父 agent 的 parent context budget 只允许承载路由、任务状态、worker id、artifact path、门禁结果和最终报告。Do not perform medical PPT planning in the parent thread。父 agent 必须 dispatch the 医学上游 worker before reading full source text；资料理解、Figure inventory、`ppt_plan.json`、speaker notes 和 prompt 写作都由子 agent 完成，父 agent 只接收 structured artifacts only。

Do not ask the user to approve sub-agent spawning。子 agent 派发是 skill 执行流程的一部分；do not ask for a reply such as a permission phrase。

## 任务目录

```text
output/yixueAIganhuo-PPT/<run_id>/
  assets/
  figures/
  plans/
  prompts/
  slides/
  slide_results/
  editppt_run/
  notes_manifest.json
  logs/
  reports/
  final/
  task_state.json
```

## 核心执行流

1. 父 agent 创建任务目录和 `task_state.json`。
2. 父 agent 先确认页数：固定问“请问这次要生成多少页 PPT？”；Do not default to any page count；Do not offer preset page-count choices；写入 `target_slide_count_confirmed` 和 `TARGET_SLIDE_COUNT`。
3. 父 agent 派发医学上游 worker，不在父线程里做医学 PPT 规划。
4. 上游 worker 写出 `source_inventory.json`、`figure_inventory.json`、`plans/ppt_plan.json`、speaker notes 和 `prompts/slideNN.txt`。
5. 父 agent 校验 slide id、页数、讲稿、Figure 绑定和 prompt 文件。
6. 父 agent 运行 prompt 门禁：

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-prompt.py \
  --prompt <task>/prompts/slideNN.txt \
  --slide-number <N>
```

摘要式 prompt、只写 "medical academic style" 的 prompt、缺少版式几何/证据绑定/负面约束/连续性规则的 prompt 不得进入页面生成 worker。

7. 父 agent 派发页面生成 worker：
   - slide 1 先生成。
   - slide 2 依赖 slide 1。
   - slide 3+ 依赖 slide 1 和 slide 2。
8. 页面生成 worker 只使用 `editppt image generate/edit/batch`，写出 `slides/slideNN.png` 和 `slide_results/slideNN.json`。
9. 第一张页面图完成后，父 agent 必须先运行真实页面图门禁：

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-ready.py \
  --slide <task>/slides/slide01.png \
  --result <task>/slide_results/slide01.json
```

Do not call `editppt prepare` until this gate passes. 合格页面图必须有 `slides/slideNN.png`、`slide_results/slideNN.json`、`status: "IMAGE_READY"`、`passed: true`、`editppt image generate/edit/batch` provenance、16:9 尺寸和 nonblank 内容。禁止 blank or white placeholder、纯色/低方差占位图、为了初始化 `editppt_run` 而创建的 `slides/sources/slideNN.png`，也禁止对 placeholder `source.png` 手写 page manifest。

10. 门禁通过后，父 agent 创建下游 run：

```bash
editppt prepare <task>/slides/slide01.png --job-dir <task>/editppt_run
```

11. 后续页面图完成后，父 agent 先运行同一个门禁：

```bash
python yixueAIganhuo-PPT/scripts/validate-slide-ready.py \
  --slide <task>/slides/slideNN.png \
  --result <task>/slide_results/slideNN.json
```

12. 只有门禁通过的页面图才能追加到同一个 run：

```bash
editppt run add-page <task>/editppt_run <task>/slides/slideNN.png --source-page <N>
```

13. 父 agent 用 `editppt run next` 派发 page worker：

```bash
python yixueAIganhuo-PPT/scripts/build-page-worker-prompt.py \
  <task>/editppt_run \
  --page page_001 \
  --out <task>/editppt_run/pages/page_001/worker-prompt.md
```

14. page worker 生成 `manifest.json`、`page.pptx`、`preview.png`、`validation.json`、`page_result.json`。
15. 父 agent 通过 `editppt run record` 记录页面结果。
16. 所有页面 recorded 后，父 agent 运行：

```bash
editppt run finalize <task>/editppt_run
```

## 并发策略

- agent pool 先给医学上游 worker，用于 source understanding、Figure inventory、`ppt_plan.json`、speaker notes 和 prompt 写作。
- 上游完成后，按依赖派发多个页面生成 worker。
- 任意页面图通过 `validate-slide-ready.py` 后，立即派发对应 page worker，不等待全部页面图完成。
- 一旦已有页面图完成，页面生成并发降到 2 以内。
- agent pool gradually reallocates worker slots to page workers。
- 剩余 worker 资源优先给下游 page worker。
- page worker 并发继续受 `page_jobs.json.max_concurrent_pages` 控制。
- 同一页不能被重复派发。
- 失败页面必须先诊断 root cause，再 `editppt run reset` 后重派。

## 文件迁入要求

`yixueAIganhuo-PPT` 必须包含：

- `cli/` 下完整 `editppt` CLI。
- `scripts/build-page-worker-prompt.py`。
- `scripts/classify-task-route.py`。
- `scripts/validate-slide-prompt.py`。
- `scripts/validate-slide-ready.py`。
- `prompts/page-worker.md`。
- `prompts/medical-upstream-worker.md`。
- `prompts/medical-slide-image-worker.md`。
- `references/cli-helper.md`。
- `references/manifest-schema.md`。
- `references/page-decision-tree.md`。
- `references/medical-integrated-workflow.md`。

## 验收标准

- 只调用 `$yixueAIganhuo-PPT` 即可执行完整医学 PPT 到可编辑 PPTX workflow。
- 主 `SKILL.md` 明确说明 `yixueAIganhuo-PPT` 是唯一完整 skill。
- 主 `SKILL.md` 明确 Task Routing：research/material PDF 默认走完整制作流程；已有图像型 deck 才走直接转换流程。
- 主 `SKILL.md` 明确 Full Authoring Hard Gate：final PPTX is invalid unless prompts、GPT Image 2 slide images、slide ready preflight、page worker record 和 finalize 全部完成。
- 主 `SKILL.md` 明确 Ask the user for the target slide count、Do not default to any page count、`target_slide_count_confirmed` 和 `TARGET_SLIDE_COUNT`。
- 主 `SKILL.md` 明确 parent context budget：Do not perform medical PPT planning in the parent thread，父 agent 只收 structured artifacts only。
- 主流程不依赖 `image-to-editable-ppt/SKILL.md`。
- 主流程不引用 yixue 旧的下游可编辑化路径。
- 页面图片生成和 page worker 图片编辑都使用 `editppt image generate/edit/batch`。
- FULL_AUTHORING_FROM_SOURCE 下，`prompts/slideNN.txt` 必须通过 `scripts/validate-slide-prompt.py`，且不得使用 `@oai/artifact-tool`、python-pptx 或 direct native PPT generation 作为最终路径。
- FULL_AUTHORING_FROM_SOURCE 下，`editppt prepare` 和 `editppt run add-page` 前必须通过 `scripts/validate-slide-ready.py`，且不得使用 blank or white placeholder、`slides/sources` 占位图或缺少 `slide_results/slideNN.json` 的页面图。
- `editppt run add-page` 可用于生成页陆续完成后的增量转换。
- page worker 必须立即启动 PaddleOCR/text-hints pass immediately，并与 foreground asset separation 并行。
- page worker 对来自素材证据的前景图，应 prefer the original material file，但必须记录 `asset_provenance`，不能变成 direct crop shortcut。
- `editppt run finalize` 必须输出 final editable PPTX 和 final image-only PPTX，且两份都应从 `notes_manifest.json` 带 speaker notes；最终报告必须包含 `editable_output` 和 `image_only_output`。
- 契约测试和 CLI 编译检查通过。
