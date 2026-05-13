# Color-Key Assist

Color-key assist is opt-in. The AI mask remains the default path because sprite
backgrounds are not always flat, and automatic color-keying can remove intended
foreground highlights, outlines, props, or effects when they are close to the
background color.

Enable corner sampling when the sprite has a consistent solid or near-solid
background:

```bash
background-remover process images/sprite.aseprite output/sprite.color-key.aseprite \
  --color-key-sample-corners \
  --color-key-tolerance 24 \
  --color-key-protect-alpha 224 \
  --ai-mask-output-dir output/ai-masks \
  --color-key-mask-output-dir output/color-key-masks \
  --mask-output-dir output/combined-masks
```

Use a specific background color when corner pixels are unreliable:

```bash
background-remover process input.aseprite output.aseprite \
  --color-key-color "#ffffff" \
  --color-key-tolerance 30
```

The combined mask removes pixels that match the color key only when the AI alpha
is below `--color-key-protect-alpha`. High-confidence AI foreground pixels are
kept even if their color is close to the sampled or provided background color.

Debug output policy:

- `--ai-mask-output-dir` writes the cleaned AI mask before color-key assist.
- `--color-key-mask-output-dir` writes the color-key foreground mask.
- `--mask-output-dir` writes the final combined mask used for the output frames.

Start with tolerance values around 20 to 30 for white or near-solid backgrounds.
Raise the tolerance only after reviewing the AI, color-key, and combined masks.
