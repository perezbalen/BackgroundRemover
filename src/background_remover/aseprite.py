"""Small Aseprite reader/writer used for the CLI spike.

The implementation is intentionally narrow: it reads enough of the format to
inspect metadata, flatten RGBA image layers, and write a simple flattened
RGBA `.aseprite` file for downstream processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import struct
import zlib

ASE_MAGIC = 0xA5E0
FRAME_MAGIC = 0xF1FA

CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_TAGS = 0x2018


class AsepriteError(ValueError):
    """Raised when an Aseprite file cannot be read by this spike parser."""


@dataclass(frozen=True)
class AsepriteLayer:
    index: int
    name: str
    flags: int
    layer_type: int
    child_level: int
    blend_mode: int
    opacity: int

    @property
    def visible(self) -> bool:
        return bool(self.flags & 1)


@dataclass(frozen=True)
class AsepriteTag:
    name: str
    from_frame: int
    to_frame: int
    direction: int
    repeat: int


@dataclass
class AsepriteCel:
    layer_index: int
    x: int
    y: int
    opacity: int
    cel_type: int
    z_index: int
    width: int | None = None
    height: int | None = None
    pixels: bytes | None = None
    linked_frame: int | None = None


@dataclass
class AsepriteFrame:
    duration_ms: int
    cels: list[AsepriteCel] = field(default_factory=list)


@dataclass
class AsepriteSprite:
    width: int
    height: int
    color_depth: int
    frames: list[AsepriteFrame]
    layers: list[AsepriteLayer]
    tags: list[AsepriteTag]

    @property
    def frame_count(self) -> int:
        return len(self.frames)


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read(self, size: int) -> bytes:
        if self.pos + size > len(self.data):
            raise AsepriteError("Unexpected end of file")
        value = self.data[self.pos : self.pos + size]
        self.pos += size
        return value

    def skip(self, size: int) -> None:
        self.read(size)

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return struct.unpack_from("<H", self.read(2))[0]

    def i16(self) -> int:
        return struct.unpack_from("<h", self.read(2))[0]

    def u32(self) -> int:
        return struct.unpack_from("<I", self.read(4))[0]

    def string(self) -> str:
        size = self.u16()
        return self.read(size).decode("utf-8", errors="replace")


def read_aseprite(path: str) -> AsepriteSprite:
    with open(path, "rb") as file:
        return parse_aseprite(file.read())


def parse_aseprite(data: bytes) -> AsepriteSprite:
    reader = _Reader(data)

    file_size = reader.u32()
    if file_size != len(data):
        raise AsepriteError(f"File size mismatch: header={file_size}, actual={len(data)}")

    magic = reader.u16()
    if magic != ASE_MAGIC:
        raise AsepriteError("Not an Aseprite file")

    frame_count = reader.u16()
    width = reader.u16()
    height = reader.u16()
    color_depth = reader.u16()
    if color_depth != 32:
        raise AsepriteError(f"Only RGBA 32 bpp sprites are supported, found {color_depth} bpp")

    reader.skip(4)  # flags
    default_speed = reader.u16()
    reader.skip(8)  # reserved DWORDs
    reader.skip(1)  # transparent palette index
    reader.skip(3)
    reader.skip(2)  # color count
    reader.skip(2)  # pixel ratio
    reader.skip(8)  # grid
    reader.skip(84)

    layers: list[AsepriteLayer] = []
    frames: list[AsepriteFrame] = []
    tags: list[AsepriteTag] = []

    for _ in range(frame_count):
        frame_size = reader.u32()
        frame_start = reader.pos - 4
        frame_end = frame_start + frame_size
        frame_magic = reader.u16()
        if frame_magic != FRAME_MAGIC:
            raise AsepriteError("Invalid frame magic number")

        old_chunk_count = reader.u16()
        duration = reader.u16() or default_speed
        reader.skip(2)
        new_chunk_count = reader.u32()
        chunk_count = new_chunk_count or old_chunk_count
        frame = AsepriteFrame(duration_ms=duration)

        for _chunk_index in range(chunk_count):
            chunk_start = reader.pos
            chunk_size = reader.u32()
            chunk_type = reader.u16()
            chunk_data_size = chunk_size - 6
            chunk_data = reader.read(chunk_data_size)

            if chunk_type == CHUNK_LAYER:
                layers.append(_parse_layer(chunk_data, len(layers)))
            elif chunk_type == CHUNK_CEL:
                frame.cels.append(_parse_cel(chunk_data))
            elif chunk_type == CHUNK_TAGS:
                tags.extend(_parse_tags(chunk_data))

            if reader.pos != chunk_start + chunk_size:
                raise AsepriteError("Chunk parser lost synchronization")

        if reader.pos != frame_end:
            reader.pos = frame_end
        frames.append(frame)

    return AsepriteSprite(
        width=width,
        height=height,
        color_depth=color_depth,
        frames=frames,
        layers=layers,
        tags=tags,
    )


def _parse_layer(data: bytes, index: int) -> AsepriteLayer:
    reader = _Reader(data)
    flags = reader.u16()
    layer_type = reader.u16()
    child_level = reader.u16()
    reader.skip(4)  # default width/height
    blend_mode = reader.u16()
    opacity = reader.u8()
    reader.skip(3)
    name = reader.string()
    return AsepriteLayer(
        index=index,
        name=name,
        flags=flags,
        layer_type=layer_type,
        child_level=child_level,
        blend_mode=blend_mode,
        opacity=opacity,
    )


def _parse_cel(data: bytes) -> AsepriteCel:
    reader = _Reader(data)
    layer_index = reader.u16()
    x = reader.i16()
    y = reader.i16()
    opacity = reader.u8()
    cel_type = reader.u16()
    z_index = reader.i16()
    reader.skip(5)

    cel = AsepriteCel(
        layer_index=layer_index,
        x=x,
        y=y,
        opacity=opacity,
        cel_type=cel_type,
        z_index=z_index,
    )

    if cel_type == 0:
        cel.width = reader.u16()
        cel.height = reader.u16()
        cel.pixels = reader.read(cel.width * cel.height * 4)
    elif cel_type == 1:
        cel.linked_frame = reader.u16()
    elif cel_type == 2:
        cel.width = reader.u16()
        cel.height = reader.u16()
        compressed = reader.read(len(data) - reader.pos)
        cel.pixels = zlib.decompress(compressed)
    elif cel_type == 3:
        raise AsepriteError("Tilemap cels are not supported in Phase 1")
    else:
        raise AsepriteError(f"Unsupported cel type: {cel_type}")

    return cel


def _parse_tags(data: bytes) -> list[AsepriteTag]:
    reader = _Reader(data)
    tag_count = reader.u16()
    reader.skip(8)
    tags = []
    for _ in range(tag_count):
        from_frame = reader.u16()
        to_frame = reader.u16()
        direction = reader.u8()
        repeat = reader.u16()
        reader.skip(6)
        reader.skip(3)
        reader.skip(1)
        name = reader.string()
        tags.append(
            AsepriteTag(
                name=name,
                from_frame=from_frame,
                to_frame=to_frame,
                direction=direction,
                repeat=repeat,
            )
        )
    return tags


def flatten_frames(sprite: AsepriteSprite) -> list[bytes]:
    """Render all visible normal layers to flattened RGBA frame buffers."""

    linked_cels: dict[tuple[int, int], AsepriteCel] = {}
    flattened = []

    for frame_index, frame in enumerate(sprite.frames):
        canvas = bytearray(sprite.width * sprite.height * 4)

        cels = []
        for cel in frame.cels:
            resolved = cel
            if cel.cel_type == 1:
                if cel.linked_frame is None:
                    continue
                resolved = linked_cels.get((cel.linked_frame, cel.layer_index), cel)
            else:
                linked_cels[(frame_index, cel.layer_index)] = cel

            layer = sprite.layers[resolved.layer_index]
            if layer.layer_type != 0 or not layer.visible:
                continue
            if layer.blend_mode != 0:
                continue
            cels.append((layer.index + resolved.z_index, resolved.z_index, layer, resolved))

        for _order, _z_index, layer, cel in sorted(cels):
            _composite_cel(canvas, sprite.width, sprite.height, layer, cel)

        flattened.append(bytes(canvas))

    return flattened


def _composite_cel(
    canvas: bytearray,
    canvas_width: int,
    canvas_height: int,
    layer: AsepriteLayer,
    cel: AsepriteCel,
) -> None:
    if cel.pixels is None or cel.width is None or cel.height is None:
        return

    opacity = (layer.opacity / 255.0) * (cel.opacity / 255.0)
    source = cel.pixels

    for source_y in range(cel.height):
        target_y = cel.y + source_y
        if target_y < 0 or target_y >= canvas_height:
            continue

        for source_x in range(cel.width):
            target_x = cel.x + source_x
            if target_x < 0 or target_x >= canvas_width:
                continue

            source_index = (source_y * cel.width + source_x) * 4
            target_index = (target_y * canvas_width + target_x) * 4
            source_alpha = (source[source_index + 3] / 255.0) * opacity
            if source_alpha <= 0:
                continue

            dest_alpha = canvas[target_index + 3] / 255.0
            out_alpha = source_alpha + dest_alpha * (1.0 - source_alpha)
            if out_alpha <= 0:
                continue

            for channel in range(3):
                source_value = source[source_index + channel] / 255.0
                dest_value = canvas[target_index + channel] / 255.0
                out_value = (
                    source_value * source_alpha
                    + dest_value * dest_alpha * (1.0 - source_alpha)
                ) / out_alpha
                canvas[target_index + channel] = round(out_value * 255)
            canvas[target_index + 3] = round(out_alpha * 255)


def write_flattened_aseprite(
    path: str,
    width: int,
    height: int,
    frame_pixels: list[bytes],
    durations_ms: list[int],
    tags: list[AsepriteTag],
    layer_name: str = "Flattened",
) -> None:
    if len(frame_pixels) != len(durations_ms):
        raise AsepriteError("Frame pixel count and duration count do not match")

    frames = []
    for index, pixels in enumerate(frame_pixels):
        if len(pixels) != width * height * 4:
            raise AsepriteError(f"Frame {index} has invalid RGBA buffer length")

        chunks = []
        if index == 0:
            chunks.append(_chunk(CHUNK_LAYER, _build_layer_chunk(layer_name)))
            if tags:
                chunks.append(_chunk(CHUNK_TAGS, _build_tags_chunk(tags)))
        chunks.append(_chunk(CHUNK_CEL, _build_compressed_cel_chunk(width, height, pixels)))
        frames.append(_frame(durations_ms[index], chunks))

    header = _header(width, height, len(frame_pixels), durations_ms[0] if durations_ms else 100)
    file_size = len(header) + sum(len(frame) for frame in frames)
    header = struct.pack("<I", file_size) + header[4:]

    with open(path, "wb") as file:
        file.write(header)
        for frame in frames:
            file.write(frame)


def _header(width: int, height: int, frame_count: int, speed: int) -> bytes:
    data = bytearray()
    data += struct.pack("<IHHHHH", 0, ASE_MAGIC, frame_count, width, height, 32)
    data += struct.pack("<I", 1)  # layer opacity is valid
    data += struct.pack("<H", speed)
    data += b"\x00" * 8
    data += b"\x00"  # transparent palette entry
    data += b"\x00" * 3
    data += struct.pack("<H", 0)
    data += b"\x01\x01"
    data += struct.pack("<hhHH", 0, 0, 0, 0)
    data += b"\x00" * 84
    if len(data) != 128:
        raise AssertionError("Invalid Aseprite header size")
    return bytes(data)


def _frame(duration_ms: int, chunks: list[bytes]) -> bytes:
    body = bytearray()
    body += struct.pack("<HHH", FRAME_MAGIC, len(chunks), duration_ms)
    body += b"\x00" * 2
    body += struct.pack("<I", 0)
    for chunk in chunks:
        body += chunk
    frame_size = len(body) + 4
    return struct.pack("<I", frame_size) + body


def _chunk(chunk_type: int, data: bytes) -> bytes:
    return struct.pack("<IH", len(data) + 6, chunk_type) + data


def _build_layer_chunk(name: str) -> bytes:
    data = bytearray()
    data += struct.pack("<HHHHHHB", 3, 0, 0, 0, 0, 0, 255)
    data += b"\x00" * 3
    data += _string(name)
    return bytes(data)


def _build_compressed_cel_chunk(width: int, height: int, pixels: bytes) -> bytes:
    data = bytearray()
    data += struct.pack("<HhhB", 0, 0, 0, 255)
    data += struct.pack("<Hh", 2, 0)
    data += b"\x00" * 5
    data += struct.pack("<HH", width, height)
    data += zlib.compress(pixels)
    return bytes(data)


def _build_tags_chunk(tags: list[AsepriteTag]) -> bytes:
    data = bytearray()
    data += struct.pack("<H", len(tags))
    data += b"\x00" * 8
    for tag in tags:
        data += struct.pack(
            "<HHBH",
            tag.from_frame,
            tag.to_frame,
            tag.direction,
            tag.repeat,
        )
        data += b"\x00" * 6
        data += b"\x00\x00\x00"
        data += b"\x00"
        data += _string(tag.name)
    return bytes(data)


def _string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<H", len(encoded)) + encoded
