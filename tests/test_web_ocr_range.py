import json
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


def test_range_controls_are_pdf_only_and_opening_does_not_save_or_call_coach(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    pdf = materials.add(user.user_id, "scan.pdf", image_book(4))
    txt = materials.add(user.user_id, "text.txt", "已有文字。".encode())
    before = {
        path: path.read_bytes()
        for path in (materials.database_path, directory / "coach_conversations.db")
    }
    html = client.get(f"/web/materials/{pdf}/read?page=2").text
    assert 'id="ocr-range-open"' in html and 'id="ocr-range-form"' in html
    assert 'id="ocr-range-start" type="number" min="1" max="4"' in html
    assert 'aria-label="本批逐页识别结果"' in html
    assert "每批最多 5 页" in html and "放弃本批全部未保存结果" in html
    assert 'id="ocr-range-form"' not in client.get(f"/web/materials/{txt}/read").text
    assert all(path.read_bytes() == data for path, data in before.items())
    assert calls == []


def test_approving_one_page_does_not_approve_other_pages_and_preserves_original(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    raw = image_book(4)
    identity = materials.add(user.user_id, "scan.pdf", raw)
    path = f"/web/materials/{identity}"

    # Only the existing per-page approval endpoint can persist recognized text.
    # Extract its CSRF from the reader panel, not from a test-only API.
    import re

    csrf = re.search(r'data-csrf="([^"]+)"', client.get(path + "/read").text)[1]
    native = materials.chunks(user.user_id, identity)
    learning = (directory / "coach_conversations.db").read_bytes()
    for page in (1, 3):
        info = client.get(path + f"/ocr?page={page}").json()
        response = client.post(
            path + "/ocr",
            data={
                "csrf": csrf,
                "page": str(page),
                "text": f"第{page}页：经核对的文字。",
                "confidence": "90",
                "digest": info["digest"],
            },
        )
        assert response.status_code == 200
        assert materials.ocr_page(user.user_id, identity, 2)["state"] == "missing"
    assert materials.get(user.user_id, identity)["readable_pages"] == 3
    kept = materials.chunk(user.user_id, identity, native[0]["chunk_id"])
    assert {key: kept[key] for key in ("chunk_id", "locator", "content")} == {
        key: native[0][key] for key in ("chunk_id", "locator", "content")
    }
    assert materials.original(user.user_id, identity)["content"] == raw
    assert (
        directory / "coach_conversations.db"
    ).read_bytes() == learning and calls == []


def test_client_range_guard_bounds_work_before_any_ocr_or_network():
    node = shutil.which("node")
    if node is None and Path("C:/Program Files/nodejs/node.exe").is_file():
        node = "C:/Program Files/nodejs/node.exe"
    if node is None:
        pytest.skip("Node is needed for the client range guard")
    module = (Path(__file__).resolve().parents[1] / "api/static/book-ocr.mjs").as_uri()
    script = """
import assert from 'node:assert/strict';
const {ocrPageRange} = await import(MODULE);
assert.deepEqual(ocrPageRange(1,5,208),[1,2,3,4,5]);
assert.deepEqual(ocrPageRange(208,208,208),[208]);
for (const args of [[1,6,208],[0,2,208],[3,2,208],[207,209,208],[1.5,2,208],[1,2,1501],[NaN,2,208],[1,Infinity,208],[true,2,208]]) {
    assert.throws(()=>ocrPageRange(...args));
}
""".replace("MODULE", json.dumps(module))
    subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_cancelled_worker_that_never_settles_preserves_reviewable_drafts(tmp_path):
    node = shutil.which("node")
    if node is None and Path("C:/Program Files/nodejs/node.exe").is_file():
        node = "C:/Program Files/nodejs/node.exe"
    if node is None:
        pytest.skip("Node is needed for the OCR client regression")
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
        [node, str(root / "tests/ocr_range_client.mjs"), module.as_uri()],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
