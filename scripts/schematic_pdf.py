"""Normalize PDF metadata and document IDs without changing schematic content."""

from pathlib import Path
import re
import subprocess
import tempfile


def normalize_pdf(path):
    path = Path(path).resolve()
    with tempfile.TemporaryDirectory(prefix="mica-pdf-") as temp:
        qdf = Path(temp) / "sheet.qdf"
        subprocess.run(
            ["qpdf", "--qdf", "--object-streams=disable", str(path), str(qdf)],
            check=True,
            capture_output=True,
        )
        data = qdf.read_bytes()

        def fixed_date(match):
            value = match[1] + b"(D:20000101000000Z)"
            if len(value) > len(match[0]):
                raise ValueError("unexpected short PDF date")
            return value.ljust(len(match[0]), b" ")

        data = re.sub(rb"(/(?:CreationDate|ModDate)\s*)\(D:[^)]*\)", fixed_date, data)
        # Preserve byte offsets in QDF; let qpdf derive both IDs from fixed content.
        data = re.sub(rb"/ID\s*\[[^]]*\]", lambda match: b" " * len(match[0]), data)
        qdf.write_bytes(data)
        subprocess.run(
            [
                "qpdf",
                "--deterministic-id",
                "--object-streams=generate",
                str(qdf),
                str(path),
            ],
            check=True,
            capture_output=True,
        )
