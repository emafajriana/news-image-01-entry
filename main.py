#!/usr/bin/env python3
"""Write our news front page to the make.fun output location.

The picture ships in this repository as ``entry.png`` next to this file.
Before copying, the program checks the file against the competition's
own limits (a whole PNG or JPEG, at most 1 MiB, at most 1024 by 1024
pixels), then copies it, byte for byte, to ``entry.png`` inside the
output directory (``MAKEFUN_OUTPUT_DIR`` when set, otherwise
``/output``). Two runs always write the same bytes: the source file is
never modified.
"""

import os
import struct
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().with_name("entry.png")
MAX_BYTES = 1_048_576
MAX_SIDE = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Read (width, height) from the PNG IHDR chunk."""
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ValueError("PNG file has no IHDR chunk")
    return struct.unpack(">II", data[16:24])


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Read (width, height) from the first JPEG SOF0/SOF2 segment."""
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            raise ValueError("JPEG segment does not start with a marker")
        marker = data[pos + 1]
        length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if marker in (0xC0, 0xC2):
            height, width = struct.unpack(">HH", data[pos + 5 : pos + 9])
            return width, height
        pos += 2 + length
    raise ValueError("JPEG file has no SOF segment")


def check_image(data: bytes) -> str:
    """Validate size and dimensions; return the detected format name."""
    if len(data) > MAX_BYTES:
        raise ValueError(f"image is {len(data)} bytes, over the {MAX_BYTES} cap")
    if data.startswith(PNG_SIGNATURE):
        width, height = png_dimensions(data)
        kind = "PNG"
    elif data.startswith(JPEG_SIGNATURE):
        width, height = jpeg_dimensions(data)
        kind = "JPEG"
    else:
        found = data[:4].hex() if data else "no bytes (empty file)"
        raise ValueError(f"unsupported image format: found {found}")
    if width > MAX_SIDE or height > MAX_SIDE:
        raise ValueError(f"image is {width}x{height}, over the {MAX_SIDE}px cap")
    return f"{kind} {width}x{height}"


def main() -> int:
    data = SOURCE.read_bytes()
    description = check_image(data)
    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "entry.png"
    with target.open("wb") as handle:
        handle.write(data)
    written = target.stat().st_size
    if written != len(data):
        raise IOError(f"wrote {written} of {len(data)} bytes to {target}")
    print(f"wrote {target} ({written} bytes, {description})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
