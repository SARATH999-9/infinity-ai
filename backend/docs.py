"""Pulls plain text out of PDF and Word (.docx) files."""
import base64
import binascii
import io


def extract_text(name: str, data_b64: str) -> str:
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("The file could not be read.")
    if len(raw) > 6_000_000:
        raise ValueError("That document is larger than 6 MB.")
    lower = name.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError("This PDF is password protected.")
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:60])
    elif lower.endswith(".docx"):
        import docx
        d = docx.Document(io.BytesIO(raw))
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        text = "\n".join(parts)
    else:
        raise ValueError("Only PDF and Word (.docx) documents are supported.")
    text = text.strip()
    if not text:
        raise ValueError("No readable text found. It may be a scanned document.")
    return text[:30000]