"""Turns a resume and/or job description (PDF, DOCX, TXT, MD) into clean text.

No LLM is involved. Cleaning is deliberately minimal: aggressive regex cleanup can mangle
real content, and the planner's LLM copes fine with slightly messy text.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, model_validator

# About 5k tokens: plenty for a resume, and it protects free-tier LLM token limits.
MAX_CHARS = 20_000
SUPPORTED_SUFFIXES = (".pdf", ".docx", ".txt", ".md")


class IngestionError(Exception):
    """The input could not be turned into usable text."""


class InterviewSource(BaseModel):
    """Cleaned input for the planner. At least one of the two texts is present."""

    resume_text: str | None = None
    jd_text: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> InterviewSource:
        if not (self.resume_text or self.jd_text):
            raise ValueError("provide a resume, a job description, or both")
        return self


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)
_BULLETS = "•▪●◦‣∙▫■□➢➤"
_HYPHEN_BREAK_RE = re.compile(r"([a-z])-\n([a-z])")  # "devel-\nopment" -> "development"
_SPACES_RE = re.compile(r"[ \t]+")
_BLANK_RUNS_RE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalize unicode and whitespace, and standardize bullets to '- '."""
    # NFKC also repairs PDF ligatures (the single character "ﬁ" becomes "fi").
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)

    lines = []
    for line in text.split("\n"):
        line = _SPACES_RE.sub(" ", line).strip()
        if line and line[0] in _BULLETS:
            line = "- " + line[1:].lstrip()
        lines.append(line)

    text = _BLANK_RUNS_RE.sub("\n\n", "\n".join(lines))
    return text.strip()


def prepare_text(raw: str, label: str) -> str:
    """Clean text and apply the guardrails. Also use this directly for pasted text."""
    text = clean_text(raw)
    if not text:
        raise IngestionError(
            f"No text found in {label}. Scanned or image-only PDFs are not supported (no OCR)."
        )
    if len(text) > MAX_CHARS:
        raise IngestionError(
            f"{label} is {len(text):,} characters; the limit is {MAX_CHARS:,}. "
            "Trim it and try again."
        )
    return text


# ---------------------------------------------------------------------------
# Readers (one per file type)
# ---------------------------------------------------------------------------


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise IngestionError(f"{path.name} is encrypted; remove the password first.")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Could not read {path.name} as a PDF: {exc}") from exc


def _read_docx(path: Path) -> str:
    from docx import Document

    try:
        doc = Document(str(path))
    except Exception as exc:
        raise IngestionError(f"Could not read {path.name} as a Word document: {exc}") from exc

    parts = [paragraph.text for paragraph in doc.paragraphs]
    # Resumes often put content in tables. Merged cells repeat their text in python-docx,
    # so consecutive duplicates are dropped. Table text follows the paragraphs.
    for table in doc.tables:
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                value = cell.text.strip()
                if value and (not cells or cells[-1] != value):
                    cells.append(value)
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _read_plain(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError(f"{path.name} is not valid UTF-8 text.") from exc


_READERS = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".txt": _read_plain,
    ".md": _read_plain,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_document(path: str | Path, label: str = "document") -> str:
    """Read a file and return cleaned, validated text."""
    path = Path(path)
    if not path.is_file():
        raise IngestionError(f"File not found: {path}")

    suffix = path.suffix.lower()
    reader = _READERS.get(suffix)
    if reader is None:
        supported = ", ".join(SUPPORTED_SUFFIXES)
        raise IngestionError(f"Unsupported file type {suffix!r} for {label}. Use: {supported}")

    return prepare_text(reader(path), f"{label} ({path.name})")


def build_source(
    resume_path: str | Path | None = None,
    jd_path: str | Path | None = None,
) -> InterviewSource:
    """Load whichever files were given. At least one is required."""
    if resume_path is None and jd_path is None:
        raise IngestionError("Provide a resume, a job description, or both.")

    return InterviewSource(
        resume_text=load_document(resume_path, "resume") if resume_path else None,
        jd_text=load_document(jd_path, "job description") if jd_path else None,
    )