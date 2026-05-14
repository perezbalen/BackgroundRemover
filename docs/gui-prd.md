# PRD: Desktop GUI for Aseprite Background Remover

## Overview

Build a local desktop GUI for the existing `background-remover` pipeline. The
GUI should make background removal feel like an interactive creative tool:
open an image or `.aseprite` file, preview the source, choose a model and
cleanup settings, process locally, inspect the result, then save or drag the
output to the file manager.

This PRD intentionally scopes the first GUI as a focused desktop app, not a full
image editor. The existing CLI remains the source of processing behavior, while
the GUI provides safer defaults, visual feedback, and discoverable controls for
the current command flags.

## Interpreted Intent

The requested GUI is not just a button that wraps the CLI. The intent is to make
the app practical for visual iteration:

- The user should trust what will be processed before they run it.
- Animated `.aseprite` files should feel native, with playback in the preview
  instead of a static first frame.
- Model and cleanup settings should be understandable without reading CLI docs.
- All current flags should remain available, but the common path should stay
  simple.
- Drag and drop should work both ways: dropping an input onto the app and
  dragging a completed output into File Explorer or another file manager.
- The original file should never be modified.

The product should correct the spelling in the UI and docs to `.aseprite`.

## Goals

- Provide a desktop GUI for still images and animated `.aseprite` inputs.
- Support drag-and-drop input loading.
- Show input and output previews side by side.
- Play animated `.aseprite` previews using source frame durations.
- Expose model selection with practical quality, speed, and license guidance.
- Expose every current processing flag through user-friendly controls.
- Save outputs through a standard file picker and by dragging the output preview
  to the OS file manager.
- Surface progress, warnings, generated artifacts, and processing reports.
- Keep processing local and CPU-first, matching the current CLI architecture.

## Non-Goals

- Replacing Aseprite or adding pixel-level editing tools.
- Training, fine-tuning, or bundling a custom model.
- Cloud processing.
- Reworking the background-removal algorithm as part of the first GUI milestone.
- Preserving original layer structure beyond the current flattened-output
  policy.
- Building a public web app.

## Users

Primary user:

- A creator or game developer preparing animated sprites from video or image
  sources who wants quick visual iteration without typing commands.

Secondary users:

- Pixel artists comparing background-removal models.
- Developers batch-cleaning sprites while checking mask stability.
- Non-CLI users who need a safe local tool with clear output behavior.

## Product Shape

### Recommended App Type

Use a native desktop app. Dragging generated files from the app into the file
manager is an operating-system integration that is more reliable in desktop UI
toolkits than in a browser-based local web UI.

Recommended first stack:

- Python UI: `PySide6` or `PyQt6`.
- Processing: call shared Python functions directly, not through shelling out to
  the CLI.
- Image decoding and still previews: Pillow.
- `.aseprite` decoding and animation data: existing
  `background_remover.aseprite` reader and `flatten_frames`.
- Worker execution: background `QThread` or worker pool so the UI stays
  responsive during model loading and frame processing.

### App Name

Working title: **Aseprite Background Remover**.

## Core Workflow

1. User opens the app.
2. User drops a still image or `.aseprite` file onto the input area, or chooses
   **Open** from a file picker.
3. App validates the file and shows metadata:
   file type, dimensions, frame count, duration, layers, and tags when present.
4. App shows a live input preview.
   For animated `.aseprite`, playback starts automatically but can be paused.
5. User chooses a model and adjusts settings.
6. User clicks **Process**.
7. App shows progress by frame, elapsed time, and current stage.
8. App shows the processed output preview, synchronized with the input preview.
9. User reviews warnings, masks, and optional artifacts.
10. User saves with **Save As** or drags the output preview into the file
    manager.

## Main UI

### Layout

Use a restrained utility layout:

- Top toolbar:
  **Open**, **Process**, **Cancel**, **Save As**, output drag handle, and status.
- Main canvas:
  side-by-side preview panes for **Input** and **Output**.
- Preview controls:
  play/pause, frame scrubber, current frame number, zoom, checkerboard
  background toggle, fit/actual-size toggle.
- Right settings panel:
  model, cleanup, color key, output artifacts, report warnings, and advanced
  options.
- Bottom panel:
  progress, warnings, report summary, and generated artifact links.

Avoid a landing page. The first screen should be the usable workspace with an
empty drop zone in the input preview pane.

### Preview Behavior

Input preview:

- Static images render immediately.
- `.aseprite` files are flattened using the current read path and animated using
  each frame's duration.
- Unsupported `.aseprite` features should not block preview if the current
  parser can flatten the file. Unsupported metadata should be shown as a
  non-blocking note.

Output preview:

- Disabled until processing succeeds.
- Static image outputs render as transparent PNG previews.
- `.aseprite` outputs play with preserved frame durations.
- Output animation should stay frame-synchronized with input when both previews
  are playing.
- Users can switch output view between result, final mask, AI mask, color-key
  mask, and contact sheet when those artifacts exist.

Preview rendering requirements:

- Show transparency with a checkerboard background by default.
- Keep stable dimensions so loading text, errors, and playback controls do not
  move the layout.
- Keep previews interactive during long processing, except while the specific
  frame image is being replaced.

## Drag And Drop

### Opening Inputs

The app must accept file drops onto:

- Empty workspace.
- Input preview pane.
- App window background.

Supported dropped input types:

- `.aseprite`
- `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`

Drop validation:

- If multiple files are dropped, load the first supported file and list the
  skipped files in a small notice.
- If an unsupported file is dropped, show a clear validation error.
- If the current project has unsaved generated output, ask before replacing the
  input.

### Saving Outputs By Dragging

The output preview should become draggable after processing succeeds.

Expected behavior:

- Dragging the output preview or drag handle to File Explorer, Finder, or a Linux
  file manager copies the generated output file.
- For `.aseprite` input, the dragged file should be the processed `.aseprite`.
- For still-image input, the dragged file should be the processed RGBA `.png`.
- If the user has not chosen an output path, the app writes the result to a
  managed temporary export file first, then exposes that file URL to the OS drag
  operation.
- The UI must make the output filename visible before dragging.
- Dragging is disabled while processing is running or after an error.

Implementation note:

- Desktop toolkits normally require a real file path for file-manager drops.
  The GUI should use OS file drag data, for example Qt `QDrag` plus
  `QMimeData` file URLs, backed by an existing output or temporary file.

## Settings UX

The settings panel should use progressive disclosure:

- **Quick Settings** for model and common cleanup choices.
- **Cleanup** for mask cleanup controls.
- **Color Key** for near-solid background workflows.
- **Outputs** for generated artifacts.
- **Advanced** for cache, overwrite, logging, dry run, and report thresholds.

Controls should use plain names and helper text, not raw CLI flag names as the
primary label. CLI names can appear in tooltips or an optional command preview.

### Model Selection

Control:

- Searchable select menu with model name, role, and speed expectation.

Models:

- `isnet-anime`
- `isnet-general-use`
- `bria-rmbg`
- `birefnet-general-lite`
- `birefnet-general`
- `birefnet-portrait`
- `birefnet-dis`
- `birefnet-hrsod`
- `birefnet-cod`
- `birefnet-massive`
- `u2net`
- `u2netp`
- `u2net_human_seg`
- `silueta`

Model metadata shown in UI:

- Best for: stylized, general, portrait/human, speed fallback, high quality.
- Expected CPU cost: fast, medium, slow, very slow.
- Download status: cached or not cached.
- License note where relevant, especially `bria-rmbg`.

Product note:

- The current CLI code defaults to `bria-rmbg`, while `README.md` still states
  `isnet-anime` in one section. Resolve this before release so the GUI, CLI, and
  docs agree on the default.

### Processing Flags To Expose

The GUI must expose the current flags through the following controls.

| CLI behavior | GUI control | Default |
| --- | --- | --- |
| input path | Open/drop input file | None |
| output path | Save As path, suggested automatically | Derived from input |
| `--model` | Model select | CLI default |
| `--model-cache-dir` | Model cache folder picker | `.cache/rembg-models` |
| `--overwrite` | Replace existing output checkbox or overwrite prompt | Off |
| `--dry-run` | Validate settings button | Off |
| `--quiet` | Minimal logs checkbox | Off |
| `--verbose` / `-v` | Diagnostics level select: Normal, Verbose, Debug | Normal |
| `--frame-output-dir` | Export processed frames folder | Off |
| `--mask-output-dir` | Export final masks folder | Off |
| `--ai-mask-output-dir` | Export AI masks folder | Off |
| `--color-key-mask-output-dir` | Export color-key masks folder | Off |
| `--mask-output` | Export still-image mask path | Off |
| `--report-output` | Export JSON report path | Off by default, suggested for animations |
| `--contact-sheet-output` | Export contact sheet path | Off |
| `--preview-output` | Export animated GIF preview path | Off |
| `--area-jump-threshold` | Mask area warning threshold slider/input | `0.25` |
| `--bbox-jump-threshold` | Motion warning threshold input in pixels | `32` |
| `--no-cleanup` | Cleanup enabled toggle | On |
| `--alpha-threshold` | Alpha threshold slider/input with auto/none state | None |
| `--min-artifact-size` | Remove specks smaller than N pixels | `4` |
| `--fill-hole-size` | Fill holes up to N pixels | `0` |
| `--keep-largest-component` | Keep largest foreground object toggle | Off |
| `--feather-radius` | Edge feather slider/input | `0.0` |
| `--color-key-sample-corners` | Sample background from corners toggle | Off |
| `--color-key-color` | Background color picker and hex/RGB input | Empty |
| `--color-key-tolerance` | Color match tolerance slider/input | `24` |
| `--color-key-protect-alpha` | Protect confident foreground slider/input | `224` |

Secondary command support:

- `--list-models`: represented by model select contents and cache status.
- `--version`: represented by an About dialog and diagnostics copy.
- `inspect`: represented by the input metadata panel.
- `rebuild-noop`: optional developer tool named **Rebuild Without Removal**.
- `benchmark-image`: optional comparison mode named **Compare Models**, with
  input file, output folder, model multi-select for `--models`, model cache
  folder, overwrite, and logging controls.

## Presets

Provide presets to guide non-CLI users without hiding advanced settings.

Recommended presets:

- **Balanced Sprite**: default model, cleanup enabled, conservative artifact
  removal, no color key.
- **Stylized Character**: `isnet-anime`, cleanup enabled, low feather.
- **Fast Draft**: `u2netp` or `silueta`, cleanup enabled, minimal artifacts.
- **Near-Solid Background**: cleanup enabled, color-key corner sampling enabled.
- **Raw Model Output**: cleanup disabled, no color key, mask export suggested.

Changing a preset updates controls but does not process automatically.

## Output Naming

Suggested names:

- Still image: `<input-stem>.transparent.png`
- Aseprite animation: `<input-stem>.processed.aseprite`
- Masks: `<input-stem>.masks/`
- Processed frames: `<input-stem>.frames/`
- AI masks: `<input-stem>.ai-masks/`
- Color-key masks: `<input-stem>.color-key-masks/`
- JSON report: `<input-stem>.report.json`
- Contact sheet: `<input-stem>.contact.png`
- GIF preview: `<input-stem>.preview.gif`

The app should avoid overwriting by default and show an explicit replace prompt
when a path already exists.

## Processing Behavior

The GUI should call shared processing functions directly. If the current CLI
logic is too tightly coupled to printing and argparse, first extract a service
layer that both CLI and GUI can use.

Service API goals:

- Load and validate input metadata.
- Produce flattened preview frames and durations.
- Run still-image removal.
- Run `.aseprite` removal.
- Emit progress events per frame and per stage.
- Emit warnings and generated artifact paths.
- Support cancellation between frames.
- Return structured success or error objects.

The GUI should not parse terminal output to infer progress.

## Error Handling

Errors should be specific and recoverable:

- Missing input file.
- Unsupported extension.
- Unsupported `.aseprite` feature.
- Output already exists.
- Model download failure.
- Model load failure.
- Missing dependency.
- Invalid setting value.
- Insufficient permissions for output location.

Display errors near the action that caused them and keep the previous successful
output preview visible until a new run succeeds.

## Progress And Cancellation

Processing can be slow on CPU, so progress must be explicit:

- Stage: loading model, reading input, processing frame, writing output, writing
  artifacts.
- Frame progress: `12 / 80`.
- Elapsed time.
- Average seconds per frame after at least one frame.
- Current model name.
- Cancel button.

Cancellation should stop after the current frame finishes, clean up incomplete
temporary files, and leave existing saved outputs untouched.

## Report And Warning UX

The GUI should summarize report warnings without forcing the user to open JSON.

Warnings to surface:

- Mask area jump warnings.
- Bounding-box jump warnings.
- Flattened layer policy.
- Unsupported or unpreserved metadata.
- Color-key risk when foreground colors are close to the selected background.

Report panel:

- Warning count.
- Clickable frame warnings that jump preview scrubber to the frame.
- Exported JSON report path if enabled.
- Metadata policy summary.

## Accessibility And UX Quality

- All controls must be keyboard reachable.
- Buttons need clear labels and tooltips for icon-only controls.
- Sliders must also have numeric inputs for precise values.
- Long file paths should truncate in the middle and show full path in tooltip.
- The preview panes should retain layout size while images load.
- Destructive actions such as replacing an existing output require confirmation.
- The app should remember recent input folders, output folders, model choice,
  and cache directory.

## Non-Functional Requirements

- Runs locally without Nvidia CUDA.
- Does not modify the source file.
- Keeps the UI responsive while processing.
- Handles missing cached models with clear download messaging.
- Works offline after selected models are cached.
- Produces deterministic results for the same input and settings.
- Uses the same processing defaults as the CLI.
- Does not write generated artifacts into source-controlled folders unless the
  user explicitly chooses those paths.

## Implementation Milestones

### Milestone 1: Shared Processing Service

- Extract CLI processing into reusable functions with structured progress.
- Keep CLI behavior and tests passing.
- Add cancellation points between frames.
- Add typed result objects for output paths, warnings, and timing.

### Milestone 2: Preview Shell

- Build the desktop window, input drop zone, and file picker.
- Render still-image previews.
- Render `.aseprite` animation previews using existing frame durations.
- Show input metadata.

### Milestone 3: Processing UI

- Add model selection and quick settings.
- Run still-image and `.aseprite` processing from the GUI.
- Show progress and cancellation.
- Render output previews.

### Milestone 4: Full Flag Coverage

- Add cleanup, color-key, artifact, report, logging, cache, and overwrite
  controls.
- Add settings validation and command preview.
- Add generated artifact links.

### Milestone 5: Drag-Out Save

- Add output drag handle backed by a real output or temporary file.
- Verify drag-to-save behavior on Windows File Explorer first, then Linux file
  managers and macOS Finder if those platforms are targeted.
- Add fallback **Save As** behavior for platforms where drag-out is unreliable.

### Milestone 6: Polish And Validation

- Add presets.
- Add recent files and persisted settings.
- Add warning navigation by frame.
- Add packaging notes for desktop distribution.
- Run manual validation against `images/susan.png` and `images/sprite.aseprite`.

## Acceptance Criteria

- Dropping `images/susan.png` loads a still preview.
- Dropping `images/sprite.aseprite` loads an animated preview with frame timing.
- The user can process a still image and preview the transparent PNG output.
- The user can process an animated `.aseprite` and preview the output animation.
- The user can choose any supported model.
- Every current processing flag has a GUI control or deliberate secondary tool
  location.
- The UI prevents accidental overwrites by default.
- The output preview can be dragged into the file manager after processing.
- Generated output opens in the target app: PNG viewer for still images,
  Aseprite for `.aseprite`.
- The GUI displays temporal warnings from the JSON report in a readable form.
- The original input file remains unchanged.

## Open Questions

- Which OS should be the first supported drag-out target: Windows, Linux, or
  macOS?
- Should the GUI ship as a Python app for developers first or as a packaged
  executable for non-technical users?
- Should model files be downloaded on demand only, or should the first-run
  experience offer to pre-cache recommended models?
- Should the first release include model benchmarking, or should that remain a
  CLI/developer workflow until the core process UI is stable?
- Should the output preview default to result-only or a result/mask split view
  for animations?
