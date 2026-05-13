from __future__ import annotations

from background_remover.aseprite import AsepriteTag, read_aseprite, write_flattened_aseprite


def test_write_flattened_aseprite_preserves_frame_metadata_and_tags(tmp_path) -> None:
    output = tmp_path / "roundtrip.aseprite"
    width = 2
    height = 2
    frames = [
        bytes([255, 0, 0, 255] * 4),
        bytes([0, 255, 0, 255] * 4),
        bytes([0, 0, 255, 255] * 4),
    ]
    durations = [83, 120, 250]
    tags = [
        AsepriteTag(
            name="Walk",
            from_frame=0,
            to_frame=2,
            direction=0,
            repeat=0,
        )
    ]

    write_flattened_aseprite(
        str(output),
        width=width,
        height=height,
        frame_pixels=frames,
        durations_ms=durations,
        tags=tags,
        layer_name="Flattened",
    )

    sprite = read_aseprite(str(output))

    assert sprite.width == width
    assert sprite.height == height
    assert sprite.frame_count == 3
    assert [frame.duration_ms for frame in sprite.frames] == durations
    assert [(tag.name, tag.from_frame, tag.to_frame) for tag in sprite.tags] == [("Walk", 0, 2)]
    assert [layer.name for layer in sprite.layers] == ["Flattened"]
