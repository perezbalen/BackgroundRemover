# GUI Implementation Plan: Aseprite Background Remover

This plan turns the GUI PRD into implementation phases. Task boxes should be
updated from `[ ]` to `[x]` as work is completed.

Source PRD: [Desktop GUI for Aseprite Background Remover](gui-prd.md)

## Current Status

- [x] CLI can inspect `.aseprite` files.
- [x] CLI can process still images.
- [x] CLI can process animated `.aseprite` files.
- [x] CLI can export processed frames, masks, reports, contact sheets, and GIF
  previews.
- [x] CLI has model selection, cleanup, color-key, cache, overwrite, dry-run,
  and reporting flags.
- [x] GUI PRD exists in `docs/gui-prd.md`.
- [x] GUI implementation has started.

## Phase 0: Product And Technical Alignment

- [x] Resolve the default model mismatch between `src/background_remover/cli.py`
  and `README.md`.
- [x] Confirm the first supported desktop platform for drag-out saving.
- [x] Choose the GUI toolkit: recommended first choice is `PySide6`.
- [x] Decide whether first delivery is developer-run Python app or packaged
  executable.
- [x] Add GUI dependencies to `pyproject.toml` behind an optional dependency
  group, for example `gui`.
- [x] Add a GUI launch command, for example `background-remover-gui`.
- [x] Document local GUI setup in `docs/development.md` or a new GUI setup doc.

Phase 0 decisions:

- Drag-out saving targets Windows File Explorer first. Linux file managers and
  macOS Finder remain later validation targets, with Save As as the fallback.
- The GUI toolkit is `PySide6`.
- The first delivery is a developer-run Python app. Packaged executables are
  deferred to Phase 10.

## Phase 1: Shared Processing Service

- [x] Create a reusable processing module separate from `argparse` and terminal
  printing.
- [x] Define typed settings objects for still-image processing.
- [x] Define typed settings objects for `.aseprite` processing.
- [x] Define typed result objects for outputs, warnings, timings, and generated
  artifact paths.
- [x] Define progress event objects for stages, frame index, frame count, and
  elapsed time.
- [x] Move input validation into reusable functions.
- [x] Move output-path preparation into reusable functions.
- [x] Move still-image processing into the shared service.
- [x] Move `.aseprite` processing into the shared service.
- [x] Keep CLI commands using the shared service without changing CLI behavior.
- [x] Add cancellation checks between animation frames.
- [x] Add unit tests for settings conversion and validation.
- [x] Add CLI regression tests for representative commands.

## Phase 2: GUI App Scaffold

- [x] Create a GUI package, for example `src/background_remover/gui/`.
- [x] Add the GUI application entry point.
- [x] Create the main window shell.
- [x] Add top toolbar actions: Open, Process, Cancel, Save As, and About.
- [x] Add a two-pane preview area for Input and Output.
- [x] Add the right settings panel container.
- [x] Add the bottom status, progress, and warnings panel.
- [x] Add persistent app settings for recent folders, model choice, and cache
  directory.
- [x] Add a minimal smoke test that imports or launches the GUI entry point
  without starting a full processing run.

## Phase 3: Input Loading And Preview

- [x] Add file picker support for `.aseprite` and supported still-image formats.
- [x] Add drag-and-drop input support for the window and input preview pane.
- [x] Validate unsupported extensions with clear errors.
- [x] Handle multi-file drops by loading the first supported file and reporting
  skipped files.
- [x] Load still-image metadata and preview images.
- [x] Load `.aseprite` metadata through the existing reader.
- [x] Flatten `.aseprite` preview frames through the existing frame path.
- [x] Render animated `.aseprite` previews using source frame durations.
- [x] Add play and pause controls.
- [x] Add frame scrubber and current-frame display.
- [x] Add zoom, fit, actual-size, and checkerboard background controls.
- [x] Keep preview panel dimensions stable while loading, erroring, or changing
  frames.
- [x] Show input metadata: dimensions, frame count, durations, layers, and tags.
- [x] Warn about known unpreserved metadata without blocking preview.

## Phase 4: Processing Workflow

- [x] Add model select with all supported models.
- [x] Show model metadata: best use, expected CPU cost, cache status, and license
  notes.
- [x] Add quick preset selection.
- [x] Add suggested output path generation.
- [x] Add overwrite protection and replace confirmation.
- [x] Run still-image processing from the GUI worker thread.
- [x] Run `.aseprite` processing from the GUI worker thread.
- [x] Keep the UI responsive during model loading and inference.
- [x] Show processing stage, frame progress, elapsed time, and average frame
  time.
- [x] Implement Cancel so it stops after the current frame and preserves
  existing successful outputs.
- [x] Render still-image output preview after success.
- [x] Render animated `.aseprite` output preview after success.
- [x] Synchronize input and output playback when both previews are animated.
- [x] Keep the previous successful output visible if a later run fails.

## Phase 5: Full Flag Coverage

- [x] Add model cache directory picker for `--model-cache-dir`.
- [x] Add dry-run or validate-settings action for `--dry-run`.
- [x] Add logging controls for quiet, normal, verbose, and debug behavior.
- [x] Add cleanup enabled toggle for `--no-cleanup`.
- [x] Add alpha threshold control with none or auto state.
- [x] Add minimum artifact size numeric control.
- [x] Add fill-hole size numeric control.
- [x] Add keep-largest-component toggle.
- [x] Add feather radius slider and numeric input.
- [x] Add color-key corner sampling toggle.
- [x] Add explicit color picker and hex/RGB input.
- [x] Add color-key tolerance slider and numeric input.
- [x] Add protect-alpha slider and numeric input.
- [x] Add processed-frame export folder picker.
- [x] Add final-mask export folder picker.
- [x] Add AI-mask export folder picker.
- [x] Add color-key-mask export folder picker.
- [x] Add still-image mask output path picker.
- [x] Add JSON report output path picker.
- [x] Add contact-sheet output path picker.
- [x] Add GIF preview output path picker.
- [x] Add report warning threshold controls for area jump and bounding-box jump.
- [x] Add a generated command preview for users who want CLI parity.
- [x] Add validation messages for invalid numeric and color values.

## Phase 6: Reports, Artifacts, And Review Tools

- [x] Show report warning count after processing.
- [x] Show mask area jump warnings in the GUI.
- [x] Show bounding-box jump warnings in the GUI.
- [x] Let users click a frame warning to jump the preview to that frame.
- [x] Show flattened layer policy in the report panel.
- [x] Show generated artifact paths after processing.
- [x] Add buttons to reveal generated artifacts in the file manager.
- [x] Add output view modes: result, final mask, AI mask, color-key mask, and
  contact sheet when available.
- [x] Add a metadata summary for the generated output.

## Phase 7: Save And Drag-Out Export

- [x] Add Save As for still-image PNG outputs.
- [x] Add Save As for processed `.aseprite` outputs.
- [x] Add managed temporary output files when the user processes before choosing
  a final save path.
- [x] Add a visible output filename and drag handle.
- [x] Implement file drag data using real file URLs.
- [x] Disable drag-out while processing, before success, and after errors.
- [x] Verify drag-to-save into Windows File Explorer.
- [ ] Verify drag-to-save into at least one Linux file manager if Linux is a
  supported target.
- [ ] Verify drag-to-save into Finder if macOS is a supported target.
- [x] Keep Save As as a reliable fallback when OS drag-out behavior differs.

## Phase 8: Optional Secondary Tools

- [x] Add About dialog that includes app version, CLI version, Python version,
  and model cache path.
- [x] Add Rebuild Without Removal developer action for `rebuild-noop`.
- [x] Add Compare Models workflow for `benchmark-image`.
- [x] Add model multi-select for Compare Models.
- [x] Add benchmark output folder picker.
- [x] Render benchmark results as a model/time table.
- [x] Let users open benchmark output images and masks from the GUI.

## Phase 9: Testing And Validation

- [ ] Add unit tests for shared service settings and result objects.
- [ ] Add unit tests for GUI path suggestion logic.
- [ ] Add unit tests for model metadata shown in the GUI.
- [ ] Add tests for still-image preview loading.
- [ ] Add tests for `.aseprite` preview frame extraction where feasible.
- [ ] Add worker cancellation tests with a lightweight fake processor.
- [ ] Add manual validation checklist for `images/susan.png`.
- [ ] Add manual validation checklist for `images/sprite.aseprite`.
- [ ] Validate that generated `.aseprite` output opens in Aseprite.
- [ ] Validate that original input files are never modified.
- [ ] Validate offline behavior with cached models.
- [ ] Validate error messages for missing models, invalid paths, and output
  collisions.

## Phase 10: Packaging And Release

- [ ] Decide packaging tool and target formats.
- [ ] Add packaging configuration.
- [ ] Ensure model cache and generated outputs are not bundled accidentally.
- [ ] Add app icon and platform metadata.
- [ ] Add a release smoke test for a clean environment.
- [ ] Add troubleshooting notes for model downloads and CPU inference.
- [ ] Add troubleshooting notes for file drag-out behavior.
- [ ] Update `README.md` with GUI setup and usage.
- [ ] Create a release checklist for the first GUI milestone.

## First GUI Definition Of Done

- [ ] `background-remover-gui` launches the desktop app.
- [ ] Dropping `images/susan.png` loads a still preview.
- [ ] Dropping `images/sprite.aseprite` loads an animated preview.
- [ ] The input animation plays with frame timing preserved.
- [ ] The user can select any supported model.
- [ ] The user can process a still image and preview the transparent result.
- [ ] The user can process an animated `.aseprite` and preview the output
  animation.
- [ ] The user can configure every current CLI processing flag from the GUI.
- [ ] The user can save output with Save As.
- [ ] The user can drag the processed output into the file manager.
- [ ] The app shows processing progress and supports cancellation.
- [ ] The app shows report warnings in a readable way.
- [ ] The app prevents accidental overwrite by default.
- [ ] The original input file is unchanged after processing.
