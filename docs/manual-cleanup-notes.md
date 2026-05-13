# Manual Cleanup Notes

Phase 5 adds temporal warnings and visual debug exports, but some cases still
need hand cleanup in Aseprite or another pixel editor:

- Fine hair, fur, smoke, glow, and semi-transparent effects can change shape
  more than the alpha-mask heuristics can judge.
- Fast character motion, smear frames, and motion blur can produce legitimate
  area or bounding-box jumps that should not always be treated as model errors.
- Hands, props, weapons, and overlapping foreground objects can be removed when
  the model mistakes them for background.
- Shadows and contact patches may need manual restoration when they are part of
  the intended sprite style.
- The current output is flattened into one processed layer, so original editable
  layer separation is not preserved yet.

Use `--report-output`, `--contact-sheet-output`, and `--preview-output` together
when reviewing a sprite. The JSON report identifies likely flicker frames, while
the contact sheet and preview make it easier to decide whether a warning is a
real defect or expected animation movement.
