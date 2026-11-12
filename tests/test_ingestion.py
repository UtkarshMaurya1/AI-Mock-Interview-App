import pytest
from docx import Document

from app.engine.ingestion import (
    MAX_CHARS,
    IngestionError,
    InterviewSource,
    build_source,
    clean_text,
    load_document,
    prepare_text,
)


def _make_pdf(text: str) -> bytes:
    """Build a minimal valid one-page PDF containing `text` (no parentheses allowed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_position = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode()
    return out


# --- clean_text -------------------------------------------------------------


def test_bullets_become_dashes():
    assert clean_text("• Python\n▪  SQL\n● Docker") == "- Python\n- SQL\n- Docker"


def test_zero_width_characters_removed():
    assert clean_text("Py\u200bthon\ufeff") == "Python"


def test_ligatures_are_normalized():
    assert clean_text("\ufb01nance") == "finance"


def test_hyphenated_line_breaks_are_rejoined():
    assert clean_text("software devel-\nopment") == "software development"


def test_uppercase_hyphen_break_is_left_alone():
    assert clean_text("Python-\nBased") == "Python-\nBased"


def test_whitespace_and_blank_lines_collapsed():
    assert clean_text("a   b\t\tc\r\n\r\n\r\n\r\nd  ") == "a b c\n\nd"


# --- prepare_text -----------------------------------------------------------


def test_prepare_text_rejects_empty():
    with pytest.raises(IngestionError, match="No text found"):
        prepare_text("  \n \u200b ", "resume")


def test_prepare_text_rejects_oversize():
    with pytest.raises(IngestionError, match="limit"):
        prepare_text("a" * (MAX_CHARS + 1), "resume")


def test_prepare_text_accepts_exact_limit():
    assert len(prepare_text("a" * MAX_CHARS, "resume")) == MAX_CHARS


# --- load_document ----------------------------------------------------------


def test_load_txt_and_md(tmp_path):
    txt = tmp_path / "resume.txt"
    txt.write_text("• Built RAG pipelines", encoding="utf-8")
    md = tmp_path / "jd.md"
    md.write_text("# Role\nPython engineer", encoding="utf-8")
    assert load_document(txt) == "- Built RAG pipelines"
    assert load_document(md) == "# Role\nPython engineer"


def test_load_txt_with_bom(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_bytes(b"\xef\xbb\xbfHello")
    assert load_document(path) == "Hello"


def test_missing_file_raises(tmp_path):
    with pytest.raises(IngestionError, match="not found"):
        load_document(tmp_path / "nope.txt")


def test_unsupported_type_raises(tmp_path):
    path = tmp_path / "resume.rtf"
    path.write_text("hello")
    with pytest.raises(IngestionError, match="Unsupported"):
        load_document(path)


def test_empty_file_raises(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n")
    with pytest.raises(IngestionError, match="No text found"):
        load_document(path)


def test_non_utf8_text_raises(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(IngestionError, match="UTF-8"):
        load_document(path)


def test_load_docx_reads_paragraphs_and_tables(tmp_path):
    doc = Document()
    doc.add_paragraph("Utkarsh - Python Developer")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Skills"
    table.cell(0, 1).text = "Python, LangGraph"
    path = tmp_path / "resume.docx"
    doc.save(path)

    text = load_document(path)
    assert "Python Developer" in text
    assert "Skills | Python, LangGraph" in text


def test_docx_merged_cells_are_not_duplicated(tmp_path):
    doc = Document()
    table = doc.add_table(rows=1, cols=2)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "Experience"
    path = tmp_path / "merged.docx"
    doc.save(path)

    assert load_document(path).count("Experience") == 1


def test_corrupt_docx_raises(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"this is not a zip file")
    with pytest.raises(IngestionError, match="Word document"):
        load_document(path)


def test_load_pdf(tmp_path):
    path = tmp_path / "resume.pdf"
    path.write_bytes(_make_pdf("Hello PDF resume"))
    assert "Hello PDF resume" in load_document(path)


def test_corrupt_pdf_raises(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"definitely not a pdf")
    with pytest.raises(IngestionError, match="PDF"):
        load_document(path)


# --- build_source -----------------------------------------------------------


def test_build_source_requires_something():
    with pytest.raises(IngestionError):
        build_source()


def test_build_source_resume_only(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text("Python developer")
    source = build_source(resume_path=path)
    assert source.resume_text == "Python developer"
    assert source.jd_text is None


def test_build_source_both(tmp_path):
    resume = tmp_path / "resume.txt"
    resume.write_text("Python developer")
    jd = tmp_path / "jd.txt"
    jd.write_text("Hiring a backend engineer")
    source = build_source(resume_path=resume, jd_path=jd)
    assert source.resume_text == "Python developer"
    assert source.jd_text == "Hiring a backend engineer"


def test_interview_source_model_requires_one_text():
    with pytest.raises(ValueError):
        InterviewSource()