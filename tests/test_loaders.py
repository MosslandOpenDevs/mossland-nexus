"""loaders 단위 테스트"""

from src.loaders import load_documents


def test_missing_directory(tmp_path):
    docs, errors = load_documents(tmp_path / "nope")
    assert docs == []
    assert errors == []


def test_load_markdown_and_txt(tmp_path):
    (tmp_path / "a.md").write_text("# 제목\n\n마크다운 본문입니다.", encoding="utf-8")
    (tmp_path / "b.txt").write_text("텍스트 파일입니다.", encoding="utf-8")

    docs, errors = load_documents(tmp_path)

    assert errors == []
    assert {d.filename for d in docs} == {"a.md", "b.txt"}
    assert all(d.file_hash for d in docs)


def test_load_cp949_fallback(tmp_path):
    (tmp_path / "legacy.txt").write_bytes("한글 레거시 인코딩".encode("cp949"))

    docs, errors = load_documents(tmp_path)

    assert errors == []
    assert docs[0].text == "한글 레거시 인코딩"


def test_load_docx(tmp_path):
    import docx

    document = docx.Document()
    document.add_paragraph("DOCX 문단입니다.")
    document.save(str(tmp_path / "doc.docx"))

    docs, errors = load_documents(tmp_path)

    assert errors == []
    assert len(docs) == 1
    assert "DOCX 문단입니다." in docs[0].text


def test_corrupt_pdf_reported_as_error(tmp_path):
    (tmp_path / "good.md").write_text("정상 문서", encoding="utf-8")
    (tmp_path / "broken.pdf").write_bytes(b"this is not a pdf")

    docs, errors = load_documents(tmp_path)

    assert len(docs) == 1
    assert len(errors) == 1
    assert errors[0].source == "broken.pdf"


def test_unsupported_extensions_ignored(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    docs, errors = load_documents(tmp_path)
    assert docs == []
    assert errors == []


def test_image_only_pdf_reported_as_error(tmp_path):
    """텍스트가 추출되지 않는 PDF(스캔본 등)는 조용히 제외되지 않고 실패로 보고"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(tmp_path / "scan.pdf", "wb") as f:
        writer.write(f)

    docs, errors = load_documents(tmp_path)

    assert docs == []
    assert len(errors) == 1
    assert errors[0].source == "scan.pdf"


def test_empty_text_file_reported_as_error(tmp_path):
    (tmp_path / "empty.txt").write_text("   \n", encoding="utf-8")

    docs, errors = load_documents(tmp_path)

    assert docs == []
    assert len(errors) == 1
