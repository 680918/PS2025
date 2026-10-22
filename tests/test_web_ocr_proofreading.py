"""Same-page original-image proofreading preserves the existing approval boundary."""

from pathlib import Path
import shutil
import subprocess

import pytest

from coach.materials import MaterialRepository
from tests.test_web_book_reader import image_book
from tests.test_web_coach_dialogue import login
from tests.test_web_library import (
    setup as setup,
    password_hash as password_hash,
    no_real_services as no_real_services,
)


def test_proofreading_is_pdf_only_and_does_not_write_or_call_coach(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "scan.pdf", image_book(4))
    text = materials.add(user.user_id, "words.txt", "学习原文。".encode())
    paths = (materials.database_path, directory / "coach_conversations.db")
    before = {path: path.read_bytes() for path in paths}
    html = client.get(f"/web/materials/{identity}/read?page=2").text
    assert 'id="ocr-source-pane"' in html
    assert 'aria-controls="ocr-source-pane"' in html
    assert 'id="ocr-source-zoom"' in html and "放大 200%" in html
    assert 'aria-label="对照原页，可上下左右滚动" tabindex="0"' in html
    assert "重试对照原页" in html
    assert 'id="ocr-source-pane"' not in client.get(f"/web/materials/{text}/read").text
    assert all(path.read_bytes() == value for path, value in before.items())
    assert calls == []


def test_source_switches_cannot_show_a_stale_page_or_approve_another_draft(tmp_path):
    node = shutil.which("node")
    if node is None and Path("C:/Program Files/nodejs/node.exe").is_file():
        node = "C:/Program Files/nodejs/node.exe"
    if node is None:
        pytest.skip("Node is needed for the proofreading client regression")
    root = Path(__file__).resolve().parents[1]
    module = tmp_path / "book-ocr.mjs"
    shutil.copyfile(root / "api/static/book-ocr.mjs", module)
    vendor = tmp_path / "vendor/tesseract/js/dist/tesseract.esm.min.js"
    vendor.parent.mkdir(parents=True)
    vendor.write_text(
        "module.exports={createWorker:async()=>{globalThis.ocrTestFactoryCalls++;return globalThis.ocrTestWorker;}};",
        encoding="utf-8",
    )
    subprocess.run(
        [node, str(root / "tests/ocr_proofread_client.mjs"), module.as_uri()],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
