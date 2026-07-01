# Provider Configuration

`yixueAIganhuo-PPT` no longer owns a separate image-provider layer.

统一改用 `editppt image` for every slide image generation or image edit in the unified workflow. The active backend contract is configured and recorded by the `yixueAIganhuo-PPT` embedded `editppt` runtime through:

```bash
editppt setup
editppt doctor
editppt config --api-key "<key>" --base-url "<openai-compatible-base-url>" --model gpt-image-2
editppt image generate/edit/batch ...
```

## Upstream Responsibility

The upstream medical worker may write:

- `ppt_plan.json`
- per-slide prompt files
- source and Figure inventories
- asset binding instructions

The upstream worker must not call an image model directly. It must return prompt files and structured dependencies to the unified parent. The parent then dispatches slide image workers that use `editppt image generate/edit/batch`.

## Required Backend Contract for Slide Workers

The parent passes each slide image worker:

```json
{
  "image_backend": {
    "tool_name": "editppt image",
    "tool_call": "editppt image generate/edit/batch",
    "model": "gpt-image-2",
    "mode_policy": "generate-or-edit-per-slide",
    "input_context_policy": "pass source Figures and style references with editppt image edit --image"
  }
}
```

Rules for generated slide images:

- Use `editppt image generate` for text-only slide generation.
- Use `editppt image edit` or `editppt image batch` when source Figures or style references must be supplied.
- Write a complete 16:9 PPT page image to `slides/slideNN.png`.
- Preferred output size is `2560x1440`.
- Record prompt path, image inputs, backend command, dimensions, and warnings in `slide_results/slideNN.json`.

## OCR Provider

OCR provider selection is handled by the embedded `editppt` runtime during downstream page conversion. Text hints, OCR-like measurement, page-level asset extraction, and editable reconstruction are all part of the yixue single-skill workflow.
