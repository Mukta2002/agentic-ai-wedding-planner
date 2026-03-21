from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_style_guide_pdf(path: str, title: str, lines: Iterable[str]) -> str:
    """Write a minimal single-page PDF with basic text.

    - No external dependencies. Uses core PDF syntax with built-in Helvetica font.
    - Returns the saved path. Raises on write errors.
    - Very basic layout; long content may truncate.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_width, page_height = 612, 792  # Letter size (points)
    y = page_height - 72  # start 1 inch from top
    leading = 16

    # Build content stream
    content_lines = [
        "BT",
        "/F1 18 Tf",
        f"72 {y} Td ({_pdf_escape(title)}) Tj",
        "ET",
    ]
    y -= 28
    content_lines.append("BT")
    content_lines.append("/F1 11 Tf")
    for line in lines:
        if y < 72:  # simple truncation when out of space
            break
        content_lines.append(f"72 {y} Td ({_pdf_escape(str(line))}) Tj")
        content_lines.append("T*")  # move to next line
        y -= leading
    content_lines.append("ET")

    content_stream = ("\n".join(content_lines)).encode("utf-8")
    stream_len = len(content_stream)

    # PDF objects
    objs: list[bytes] = []
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objs.append(
        f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n".encode(
            "ascii"
        )
    )
    objs.append(
        b"4 0 obj\n<< /Length "
        + str(stream_len).encode("ascii")
        + b" >>\nstream\n"
        + content_stream
        + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    # Assemble file with xref
    xref_positions: list[int] = []
    body = b""
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    for obj in objs:
        # Absolute offset from start of file (after header)
        xref_positions.append(len(header) + len(body))
        body += obj

    xref_start = len(header) + len(body)
    xref = [b"xref\n", f"0 {len(objs)+1}\n".encode("ascii"), b"0000000000 65535 f \n"]

    offset = len(header)
    for pos in xref_positions:
        xref.append(f"{pos:010} 00000 n \n".encode("ascii"))
    xref_blob = b"".join(xref)

    trailer = (
        b"trailer\n<< /Size "
        + str(len(objs) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_start).encode("ascii")
        + b"\n%%EOF\n"
    )

    with out.open("wb") as f:
        f.write(header)
        f.write(body)
        f.write(xref_blob)
        f.write(trailer)

    return str(out)
