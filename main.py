"""Copy the bundled entry image to the output directory after validation.

The bundled file is always called entry.png next to this script, even
when its actual bytes are JPEG. We check the size, sniff the real format
from the magic bytes, extract the pixel dimensions, and only then copy
the file verbatim.
"""

import hashlib
import os
import struct
import sys
from pathlib import Path

LIMIT_BYTES = 1_048_576
LIMIT_DIM = 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def fail(reason: str) -> None:
    print(f"error: {reason}", file=sys.stderr)
    raise SystemExit(1)


def png_dimensions(data: bytes) -> tuple[int, int]:
    # Need at least signature (8) + length (4) + type (4) + width/height (8)
    if len(data) < 24:
        fail(f"PNG data measured {len(data)} bytes, need at least 24 bytes for IHDR (limit {LIMIT_BYTES} bytes max)")
    if data[12:16] != b"IHDR":
        fail(f"PNG is missing its IHDR chunk: found {data[12:16]!r} at offset 12, size {len(data)} bytes")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    # Walk JPEG segments looking for SOF0 (0xC0) or SOF2 (0xC2).
    pos = 2  # skip the SOI marker we already matched
    total = len(data)
    while pos + 4 <= total:
        if data[pos] != 0xFF:
            fail("corrupt JPEG: expected a segment marker")
        marker = data[pos + 1]
        # Standalone markers have no length field.
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            pos += 2
            continue
        seg_len = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if seg_len < 2 or pos + 2 + seg_len > total:
            fail("corrupt JPEG: segment length out of range")
        if marker in (0xC0, 0xC2):
            if seg_len < 7:
                fail("corrupt JPEG: frame header too short")
            # Layout after length: precision (1), height (2), width (2)
            height = struct.unpack(">H", data[pos + 5 : pos + 7])[0]
            width = struct.unpack(">H", data[pos + 7 : pos + 9])[0]
            return width, height
        if marker == 0xDA:
            break  # start of scan, no frame header found before image data
        pos += 2 + seg_len
    fail("could not locate a JPEG frame header (SOF0/SOF2)")
    return 0, 0  # unreachable, keeps type checkers quiet


def inspect_image(data: bytes) -> tuple[int, int, str]:
    if len(data) == 0:
        fail(f"bundled image is empty: measured 0 bytes, need 1..{LIMIT_BYTES} bytes")
    if len(data) > LIMIT_BYTES:
        fail(f"image size {len(data)} bytes violates the {LIMIT_BYTES} byte limit")
    if data.startswith(PNG_MAGIC):
        fmt = "PNG"
        width, height = png_dimensions(data)
    elif data[:2] == b"\xff\xd8":
        fmt = "JPEG"
        width, height = jpeg_dimensions(data)
    else:
        fail(
            f"unrecognised image format: first bytes {data[:8].hex()} "
            f"(size {len(data)} bytes, limit {LIMIT_BYTES}) are neither PNG nor JPEG"
        )
    for label, value in (("width", width), ("height", height)):
        if not 1 <= value <= LIMIT_DIM:
            fail(f"{label} measured {value}px violates the 1..{LIMIT_DIM}px limit")
    return width, height, fmt


def main() -> None:
    here = Path(__file__).resolve().parent
    source = here / "entry.png"
    if not source.is_file():
        fail(f"bundled image not found at {source}")

    payload = source.read_bytes()
    width, height, fmt = inspect_image(payload)

    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "entry.png"
    target.write_bytes(payload)

    digest = hashlib.sha256(payload).hexdigest()
    print(f"wrote {target} ({len(payload)} bytes, {width}x{height}, {fmt}, sha256={digest})")


if __name__ == "__main__":
    main()
