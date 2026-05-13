# CLI Implementation Plan: Aseprite Background Remover

This plan turns the PRD into implementation phases for a CPU-first CLI app. Task boxes should be marked from `[ ]` to `[x]` as work is completed.

## Phase 0: Project Setup

- [x] Choose the Python package layout for the CLI app.
- [x] Add a `pyproject.toml` with project metadata and CLI entry point.
- [x] Add a minimal source package, for example `src/background_remover/`.
- [x] Add a CLI module, for example `src/background_remover/cli.py`.
- [x] Add a local virtual environment setup path to the README or docs.
- [x] Add dependency groups for runtime and development tools.
- [x] Add `.gitignore` entries for virtualenvs, model caches, generated frames, and output files.
- [x] Add a simple smoke-test command that prints CLI help.

## Phase 1: Aseprite Read/Write Spike

- [x] Decide whether the first implementation uses a Python `.aseprite` parser/writer, the Aseprite CLI, or both.
- [x] Inspect `images/sprite.aseprite` metadata: canvas size, frame count, frame durations, layers, and tags.
- [x] Implement a frame export function that returns flattened RGBA frames in order.
- [x] Implement metadata extraction for frame durations.
- [x] Implement metadata extraction for animation tags if supported.
- [x] Implement a no-op rebuild command that exports frames and writes them back to a new `.aseprite`.
- [x] Verify the rebuilt no-op file opens in Aseprite.
- [x] Verify the rebuilt no-op file preserves frame count and timing.
- [x] Document unsupported `.aseprite` features found during the spike.

## Phase 2: Single-Image Background Removal

- [x] Add CPU-only background-removal dependencies.
- [x] Implement a model-session factory that reuses one session per CLI run.
- [x] Add support for the initial model list: `isnet-anime`, `birefnet-general-lite`, `isnet-general-use`, `u2netp`, and `silueta`.
- [x] Implement background removal for one PIL image.
- [x] Implement output of an RGBA image with transparent background.
- [x] Add a command or option to test one still image, using `images/susan.png`.
- [x] Export raw alpha mask PNGs for debugging.
- [x] Measure processing time for each candidate model on `images/susan.png`.
- [x] Record model quality notes in a docs file.

## Phase 3: First End-To-End Aseprite CLI

- [x] Add CLI arguments for input `.aseprite`, output `.aseprite`, and model name.
- [x] Add CLI arguments for optional processed-frame export directory.
- [x] Add CLI arguments for optional mask export directory.
- [x] Process all exported frames with one reused model session.
- [x] Rebuild the processed frames into a new `.aseprite` file.
- [x] Preserve canvas size.
- [x] Preserve frame order.
- [x] Preserve frame duration.
- [x] Print progress for each processed frame.
- [x] Print total runtime and average runtime per frame.
- [x] Run the command against `images/sprite.aseprite`.
- [x] Verify the output opens in Aseprite.

## Phase 4: Mask Cleanup Controls

- [x] Add an alpha threshold option.
- [x] Add an option to remove tiny isolated alpha artifacts.
- [x] Add an option to fill small holes in the foreground mask.
- [x] Add an option to keep the largest connected foreground component.
- [x] Add an edge feathering option.
- [x] Add an option to disable all cleanup and export raw model output.
- [x] Add mask cleanup unit tests using synthetic masks.
- [x] Compare before/after cleanup on `images/sprite.aseprite`.
- [x] Choose conservative default cleanup settings.

## Phase 5: Temporal Consistency Checks

- [ ] Compute per-frame alpha-mask difference metrics.
- [ ] Detect sudden mask area jumps between neighboring frames.
- [ ] Detect sudden bounding-box jumps between neighboring frames.
- [ ] Add warnings for likely flicker points.
- [ ] Export a JSON processing report with frame metrics.
- [ ] Add a contact sheet export showing original frame, mask, and result.
- [ ] Add a short animated preview export, such as GIF or PNG sequence, if practical.
- [ ] Document known cases where manual cleanup is still expected.

## Phase 6: Color-Key Assisted Removal

- [ ] Add optional background color sampling from corners or user-provided color.
- [ ] Add tolerance controls for near-white or near-solid backgrounds.
- [ ] Combine color-key masks with AI masks.
- [ ] Protect foreground pixels from color-key removal when AI confidence is high.
- [ ] Add preview/debug output for AI mask, color-key mask, and combined mask.
- [ ] Test on frames with white or near-solid backgrounds.
- [ ] Decide whether color-key assistance should be opt-in or automatic.

## Phase 7: Metadata And Layer Policy

- [ ] Decide the default output layer policy: flattened processed layer or original layer preservation.
- [ ] Preserve animation tags if supported by the chosen write path.
- [ ] Preserve slices if supported by the chosen write path.
- [ ] Preserve layer names where feasible.
- [ ] Add a warning when the tool flattens layers.
- [ ] Add documentation explaining what metadata is preserved.
- [ ] Add regression checks for frame count, duration, and tags.

## Phase 8: CLI Usability

- [ ] Add `--dry-run` to inspect input metadata without processing.
- [ ] Add `--list-models`.
- [ ] Add `--model-cache-dir`.
- [ ] Add `--overwrite` protection for output files.
- [ ] Add clear error messages for missing input files.
- [ ] Add clear error messages for unsupported `.aseprite` features.
- [ ] Add clear error messages for missing model files or failed downloads.
- [ ] Add logging verbosity options.
- [ ] Add examples to the README.

## Phase 9: Testing And Validation

- [ ] Add automated tests for CLI argument parsing.
- [ ] Add automated tests for mask cleanup functions.
- [ ] Add automated tests for report generation.
- [ ] Add an integration test for still-image processing.
- [ ] Add an integration test for `.aseprite` frame extraction if fixtures are lightweight enough.
- [ ] Add a manual validation checklist for `images/sprite.aseprite`.
- [ ] Compare candidate models on quality and runtime.
- [ ] Select the recommended default model.
- [ ] Document final CPU performance expectations.

## Phase 10: Packaging

- [ ] Make the CLI installable with `pip install -e .`.
- [ ] Verify the CLI works from a clean virtual environment.
- [ ] Pin or constrain dependencies enough for reproducible installs.
- [ ] Add a troubleshooting section for model downloads and CPU inference.
- [ ] Add a release checklist.
- [ ] Tag the first usable CLI milestone when complete.

## Initial Definition Of Done

- [ ] `background-remover --help` works.
- [ ] The CLI can process `images/susan.png` as a still-image smoke test.
- [ ] The CLI can process `images/sprite.aseprite`.
- [ ] The generated `.aseprite` opens successfully.
- [ ] Frame count is preserved.
- [ ] Frame duration is preserved.
- [ ] The original input file is never modified.
- [ ] A debug mask sequence can be exported.
- [ ] A processing report can be exported.
- [ ] The default path runs without Nvidia CUDA.
