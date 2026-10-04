"""Turn an uploaded document into plain text for verification."""
import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from models import DocumentSource

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 100_000


class DocumentError(ValueError):
    """The upload can't be used. The message is safe to show the user."""


def extract_text(data: bytes, filename: str) -> tuple[str, DocumentSource]:
    """Return (text, source) for a .txt or text-based .pdf upload."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError("File is too large (5 MB maximum).")

    name = filename.lower()
    if name.endswith(".pdf"):
        text, source = _pdf_text(data), DocumentSource.pdf
    elif name.endswith(".txt"):
        text, source = _txt_text(data), DocumentSource.text_file
    else:
        raise DocumentError("Unsupported file type. Upload a .txt or .pdf file, or paste the text.")

    return clean_text(text), source


def clean_text(text: str) -> str:
    """Normalise whitespace and enforce the length limit."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    cleaned = "\n".join(line for line in lines if line)
    if not cleaned:
        raise DocumentError("The document doesn't contain any text.")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise DocumentError(f"The document is too long ({MAX_TEXT_CHARS:,} characters maximum).")
    return cleaned


def _txt_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DocumentError("The text file isn't UTF-8 encoded.") from None


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, ValueError, OSError):
        raise DocumentError("The PDF couldn't be read. It may be damaged or password-protected.") from None
    if not text.strip():
        raise DocumentError(
            "No text found in the PDF. Scanned certificates aren't supported yet; "
            "paste the certificate's text instead."
        )
    return text
