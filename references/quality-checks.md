# Quality Checks

These checks apply only to the upstream medical planning worker.

## Source and Figure Inventory

- Source topic, disease area, method, cohort/model, intervention/exposure, endpoint, key result, and limitation are summarized.
- PDF Figure estimates are based on main Figure numbers, not subfigure letters.
- Raw extracted image candidates are separated from final usable evidence Figures.
- Discarded images have explicit reasons.
- Tables are not counted as Figures unless the parent explicitly requests table images.
- Final `figure_inventory.json` maps usable evidence assets to source page/caption when available.

## Plan Quality

- `ppt_plan.json` has exactly one entry per target slide.
- Slide ids and numbers are continuous.
- Every slide has role, title, core message, layout regions, references, and `speaker_notes_zh`.
- Evidence Figure bindings are medically meaningful and not decorative.
- Slide dependencies follow the style-continuity graph:
  - slide 1 has no style dependency
  - slide 2 depends on slide 1
  - slide 3+ depend on slide 1 and slide 2
- `generation_keys` are present or inferable.

## Prompt Quality

- Prompt files exist for every slide.
- Prompt files include expanded style key text, not only key names.
- Prompt files include the slide plan and medical evidence constraints.
- Prompt files forbid fake authors, institutions, dates, citations, sample sizes, P values, and unsupported statistics.
- Prompts instruct evidence Figure preservation and aspect-ratio preservation when source Figures are bound.

## Handoff Quality

- The worker returns only structured paths and status.
- The parent can dispatch slide image workers without reopening full PDF text.
- No downstream PPTX reconstruction artifacts are created by this skill.
