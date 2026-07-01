# Medical Slide Image Worker Prompt Template

```text
Generate one complete medical PPT slide image for the yixueAIganhuo-PPT single-skill workflow.

Task dir: {{TASK_DIR}}
Slide id: {{SLIDE_ID}}
Slide number: {{SLIDE_NUMBER}}
Slide plan: {{SLIDE_PLAN_PATH}}
Prompt file: {{PROMPT_FILE}}
Output image: {{OUTPUT_IMAGE}}
Result JSON: {{RESULT_JSON}}
Reference images: {{REFERENCE_IMAGES}}
Figure inputs: {{FIGURE_INPUTS}}

You own only this slide image output and its result JSON. Do not write page-level manifest.json, page.pptx, preview.png, validation.json, editppt_run state, or final deck files.

Mandatory image backend:
- Use editppt image generate/edit/batch.
- Use editppt image edit when prompt execution requires source Figure inputs or style reference images.
- Do not call legacy yixue image generation scripts.
- Do not call non-`editppt image` generation tools.
- Do not locally compose the final slide with PIL, SVG, HTML screenshots, python-pptx, @oai/artifact-tool, direct native PPT generation, or any presentation authoring shortcut.

Prompt quality gate:
- Do not accept summary-style prompts.
- The prompt file must be a rich GPT Image 2 slide prompt with expanded style-key text, slide-specific plan, concrete layout geometry, evidence/asset binding instructions, negative constraints, and continuity rules.
- If the prompt has not passed `yixueAIganhuo-PPT/scripts/validate-slide-prompt.py`, stop and return `status=failed` instead of generating from a weak prompt.
- If `editppt image` or its GPT Image 2 backend is unavailable, stop and report the blocker. Do not switch to artifact-tool, python-pptx, HTML/SVG screenshots, or native PPTX generation.

Output must be a complete 16:9 PowerPoint page image: title, body text, evidence regions, citations/notes if requested, and visual design all inside the generated image. Preferred canvas is 2560x1440.

Before returning:
1. Verify {{OUTPUT_IMAGE}} exists.
2. Verify image dimensions and record them.
3. Write {{RESULT_JSON}} with slide_id, slide_number, prompt path, output path, reference image paths, figure input paths, backend command, size_px, passed, warnings, and errors.

Return only:
output_image=<absolute path>
result_json=<absolute path>
status=passed|failed
```
