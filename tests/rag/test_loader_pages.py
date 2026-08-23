from app.rag.loader import DocumentLoader


def test_pdf_page_loader_preserves_page_boundaries(monkeypatch, tmp_path):
    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class FakeReader:
        def __init__(self, _path):
            self.pages = [FakePage("page one"), FakePage("page two")]

    monkeypatch.setattr("app.rag.loader.PdfReader", FakeReader)
    path = tmp_path / "policy.pdf"
    path.write_bytes(b"pdf")

    pages = DocumentLoader().load_pages(path)

    assert pages == [(1, "page one"), (2, "page two")]
