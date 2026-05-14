"""Build CLI-equivalent command previews for GUI settings."""

from __future__ import annotations

from pathlib import Path
import shlex

from background_remover.color_key import ColorKeyOptions
from background_remover.gui.processing_options import GuiProcessingOptions
from background_remover.mask_cleanup import MaskCleanupOptions


def build_command_preview(
    *,
    input_path: Path,
    output_path: Path,
    input_type: str,
    model_name: str,
    overwrite: bool,
    options: GuiProcessingOptions,
) -> str:
    command = ["background-remover"]
    if input_type == "aseprite":
        command += ["process", str(input_path), str(output_path)]
        _append_common_options(command, model_name, overwrite, options)
        _append_aseprite_options(command, options)
    else:
        command += ["remove-image", str(input_path), str(output_path)]
        _append_common_options(command, model_name, overwrite, options)
        if options.still_mask_output_path:
            command += ["--mask-output", str(options.still_mask_output_path)]
    return " ".join(shlex.quote(part) for part in command)


def _append_common_options(
    command: list[str],
    model_name: str,
    overwrite: bool,
    options: GuiProcessingOptions,
) -> None:
    command += ["--model", model_name]
    command += ["--model-cache-dir", str(options.model_cache_dir)]
    if overwrite:
        command.append("--overwrite")
    if options.quiet:
        command.append("--quiet")
    if options.verbose:
        command.extend(["-" + "v" * options.verbose])
    _append_cleanup_options(command, options.cleanup_options)


def _append_cleanup_options(command: list[str], options: MaskCleanupOptions) -> None:
    if not options.enabled:
        command.append("--no-cleanup")
        return
    if options.alpha_threshold is not None:
        command += ["--alpha-threshold", str(options.alpha_threshold)]
    command += ["--min-artifact-size", str(options.min_artifact_size)]
    command += ["--fill-hole-size", str(options.fill_hole_size)]
    if options.keep_largest_component:
        command.append("--keep-largest-component")
    command += ["--feather-radius", f"{options.feather_radius:g}"]


def _append_aseprite_options(command: list[str], options: GuiProcessingOptions) -> None:
    for flag, path in (
        ("--frame-output-dir", options.frame_output_dir),
        ("--mask-output-dir", options.mask_output_dir),
        ("--ai-mask-output-dir", options.ai_mask_output_dir),
        ("--color-key-mask-output-dir", options.color_key_mask_output_dir),
        ("--report-output", options.report_output_path),
        ("--contact-sheet-output", options.contact_sheet_output_path),
        ("--preview-output", options.preview_output_path),
    ):
        if path:
            command += [flag, str(path)]
    command += ["--area-jump-threshold", f"{options.area_jump_threshold:g}"]
    command += ["--bbox-jump-threshold", f"{options.bbox_jump_threshold:g}"]
    _append_color_key_options(command, options.color_key_options)


def _append_color_key_options(command: list[str], options: ColorKeyOptions) -> None:
    if not options.enabled:
        return
    if options.sample_corners:
        command.append("--color-key-sample-corners")
    if options.color:
        command += ["--color-key-color", "#{:02x}{:02x}{:02x}".format(*options.color)]
    command += ["--color-key-tolerance", f"{options.tolerance:g}"]
    command += ["--color-key-protect-alpha", str(options.protect_alpha)]
