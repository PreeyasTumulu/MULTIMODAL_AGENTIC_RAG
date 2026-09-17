"""Private uploads: what is accepted, how it is named and chunked, and who may see it.

No Postgres, Qdrant or model: the job itself is exercised end to end against the
real stack (docs/CHANGELOG.md, Day 7), these pin the rules it is built from.
"""

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from analyst import api, uploads
from analyst.chunking import SourceElement, TitleContext, chunk_document
from analyst.config import Settings
from analyst.models import Document

KEY = "s3cret-key"


def test_the_file_type_is_read_from_the_bytes_not_the_name() -> None:
    assert uploads.check_pdf(b"%PDF-1.7\n1 0 obj") is None
    assert uploads.check_pdf(b"PK\x03\x04 a zip called report.pdf") == "That is not a PDF."
    assert "over 50 MB" in str(uploads.check_pdf(b"%PDF-" + bytes(uploads.MAX_BYTES)))


def test_a_title_falls_back_to_a_tidied_file_name() -> None:
    assert uploads.title_from(None, "Q3_investor__deck.PDF") == "Q3 investor deck"
    assert uploads.title_from("  Board   minutes ", "x.pdf") == "Board minutes"
    assert uploads.title_from(None, None) == "Untitled document"


def test_the_same_bytes_are_the_same_document() -> None:
    a, b = uploads.document_id_for(b"%PDF-a"), uploads.document_id_for(b"%PDF-b")
    assert a == uploads.document_id_for(b"%PDF-a") != b and a.startswith("upload-")


def test_an_upload_chunk_states_its_title_not_a_company() -> None:
    text = "Quarterly revenue grew across every segment of the business this year, led by exports."
    el = SourceElement("upload-x:p0001:e0000", "upload-x", 1, 0, "text", text)
    chunks = chunk_document([el], None, None, context=TitleContext("Acme investor update"))
    assert [(c.ticker, c.fiscal_year) for c in chunks] == [(None, None)]
    assert chunks[0].embed_text == f"Acme investor update\n{text}"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "get_settings", lambda: Settings(admin_api_key=SecretStr(KEY)))


def status(key: str | None) -> int:
    with pytest.raises(HTTPException) as e:
        api.private(key)
    return e.value.status_code


def test_uploads_are_switched_off_until_a_key_is_configured(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty ADMIN_API_KEY= parses as SecretStr(""), not None - both mean off."""
    for unset in (None, SecretStr("")):
        monkeypatch.setattr(api, "get_settings", lambda u=unset: Settings(admin_api_key=u))
        assert status(KEY) == 503


@pytest.mark.usefixtures("configured")
def test_only_the_exact_key_opens_the_private_routes() -> None:
    assert [status(k) for k in (None, "", "s3cret", KEY + " ")] == [401] * 4
    api.private(KEY)  # no exception


@pytest.mark.usefixtures("configured")
def test_an_uploads_pages_do_not_exist_without_the_key() -> None:
    upload = Document(document_id="upload-x", source="upload")
    with pytest.raises(HTTPException) as e:
        api._visible(upload, None)
    assert e.value.status_code == 404  # not 401: its existence is private too
    api._visible(upload, KEY)
    api._visible(Document(document_id="SUN", source="corpus"), None)  # filings stay public
