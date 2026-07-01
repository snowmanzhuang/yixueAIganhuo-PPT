# Deprecated Downstream Pipeline

这些组件属于旧版 yixue downstream editable PPTX 流程，已经废弃。

Deprecated components include:

- `scripts/run_gpt_image2_slide.py`
- `scripts/run_ocr_slide.py`
- `scripts/run_ppocrv5_api_slide.py`
- `scripts/make_clean_inputs.py`
- `scripts/build_editable_pptx.py`
- `scripts/collect_codex_imagegen_output.py`
- `scripts/validate_outputs.py`
- `references/editable-pptx-pipeline.md`
- `references/codex-imagegen-orchestration.md`

## Migration Rule

Do not use this path for current work. The unified workflow keeps only the upstream medical planning and prompt-writing value from `yixueAIganhuo-PPT`.

Current execution uses:

- upstream medical planning from `yixueAIganhuo-PPT`
- slide image generation through `editppt image generate/edit/batch`
- editable reconstruction through `yixueAIganhuo-PPT` page workers
- final assembly through `editppt run finalize`

The deprecated files may remain in the repository as reference material, but they are not authoritative workflow instructions.
