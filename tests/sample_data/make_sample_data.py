"""Generate the synthetic sample files used for demos and manual testing."""

from __future__ import annotations

import pathlib
import struct
import zlib

OUT_DIR = pathlib.Path(__file__).parent

EVIDENCE_LINES = [
    "INCIDENT NOTE",
    "Reported by Jamie Placeholder",
    "Email: jamie.placeholder@example.com",
    "Phone: 555-0143",
    "Subject: unguarded machinery on the night shift.",
]


# Copied code from previous project I did
def write_pdf(path: pathlib.Path, lines: list[str]) -> None:
    """Write a minimal one-page PDF containing the given lines of text."""
    ops = ["BT", "/F1 16 Tf", "60 720 Td", "22 TL"]
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        ops.append(f"({escaped}) Tj")
        ops.append("T*")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()

    path.write_bytes(bytes(out))


def write_blank_png(path: pathlib.Path, width: int = 240, height: int = 160) -> None:
    """Write a plain white PNG, an image with no readable text at all."""
    raw = b"".join(b"\x00" + b"\xff" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    """Write every sample file into this directory."""
    write_pdf(OUT_DIR / "evidence_with_pii.pdf", EVIDENCE_LINES)
    write_blank_png(OUT_DIR / "evidence_no_text.png")
    (OUT_DIR / "not_allowed.txt").write_text(
        "A plain text file. The API should refuse this with a 422.\n"
    )


if __name__ == "__main__":
    main()
