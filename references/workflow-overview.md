# Workflow Overview

## Purpose

This reference describes the medical planning segment of the single-skill workflow.

`yixueAIganhuo-PPT` supplies medical source understanding, Figure inventory, `ppt_plan.json`, speaker notes, page dependencies, and slide prompt files. It hands those structured files to the unified parent. Slide image generation and editable PPTX conversion are also handled inside this skill through `editppt image`, page workers, and `editppt run finalize`.

## Upstream DAG

```text
Parent task request and source paths
  ↓
Medical source inspection
  ↓
Figure inventory and filtering
  ↓
Narrative and slide count planning
  ↓
ppt_plan.json
  ↓
slideNN prompt files
  ↓
Structured handoff to unified parent
```

After handoff, the unified parent dispatches slide image workers through `editppt image generate/edit/batch`, then dispatches page workers for editable reconstruction.

## Required Outputs

The upstream worker writes:

- `source_inventory.json`
- `figure_inventory.json`
- `plans/ppt_plan.json`
- `prompts/slideNN.txt`

The upstream worker returns only paths and status to the parent.

## Planning Rules

- Use concise source summaries, not full copied paper text.
- Count main Figures by main number, not subfigure letters.
- Discard non-evidence images and record why.
- Bind evidence Figures to slides only when they serve the medical narrative.
- Keep slide 1 as style baseline, slide 2 dependent on slide 1, and slide 3+ dependent on slide 1 plus slide 2.
- Include Chinese speaker notes for every slide.
- Include `generation_keys` so prompt construction can expand only the required style keys.

## Handoff

The parent receives structured artifacts and then continues with:

```text
slide image workers via editppt image
  ↓
editppt prepare on generated slide images
  ↓
page workers
  ↓
editppt run finalize
```

Do not run the deprecated downstream editable conversion path. Use the embedded page-worker workflow.
