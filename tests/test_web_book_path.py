import secrets
from uuid import uuid4

import pytest

from tests import test_web_book_section as base_tests
from tests.test_web_coach_dialogue import Forms, login

setup = base_tests.setup
password_hash = base_tests.password_hash
no_real_services = base_tests.no_real_services
choose = base_tests.choose
pdf_with_blank_middle = base_tests.pdf_with_blank_middle


def new_unit(client, book, *, title="第一单元", start="1", end="2"):
    editor = client.get(f"/web/materials/{book}/plan/new")
    form = next(row for row in Forms(editor.text).forms if "/plan/" in row["path"])
    return form["path"], {
        **form["values"],
        "title": title,
        "start_pos": start,
        "end_pos": end,
    }


def study_form(html, part=None):
    forms = [
        row["values"]
        for row in Forms(html).forms
        if row["path"] == "/web/coach/message"
        and row["values"].get("action") == "study"
    ]
    return next(row for row in forms if part is None or row["part_id"] == part)


def test_directory_edit_and_select_are_free_and_next_stays_in_unit(setup):
    _, client, repo, materials, user, _, book, calls = setup
    directory = client.get(f"/web/materials/{book}/plan")
    assert directory.status_code == 200 and "0 / 3" in directory.text
    assert repo.book_position(user.user_id, book) is None
    path, values = new_unit(client, book, title="<第一单元>")
    assert client.post(path, data=values).status_code == 200
    assert calls == []
    assert "&lt;第一单元&gt;" in client.get(f"/web/materials/{book}/plan").text
    selected = choose(client, book, 1)
    assert "学习单元 · &lt;第一单元&gt;" in selected.text
    assert "已讲解 0 / 2 段" in selected.text
    first = study_form(selected.text)
    answer = client.post("/web/coach/message", data=first)
    assert "已讲解 1 / 2 段" in answer.text
    next_id = materials.chunks(user.user_id, book)[1]["chunk_id"]
    second = study_form(answer.text, next_id)
    finished = client.post("/web/coach/message", data=second)
    assert len(calls) == 2 and "已讲解 2 / 2 段" in finished.text
    assert "已到本单元末段" in finished.text
    assert "讲解下一段 · 片段 3" not in finished.text
    assert repo.topic_part(user.user_id)["chunk_id"] == next_id
    assert client.post("/web/coach/message", data=second).status_code == 200
    assert len(calls) == 2 and len(repo.book_coverage(user.user_id, book)) == 2
    assert repo.list_knowledge(user.user_id) == []


def test_next_part_is_signed_and_old_form_resumes_exact_displayed_target(setup):
    _, client, repo, materials, user, _, book, calls = setup
    page = choose(client, book, 1)
    chunks = materials.chunks(user.user_id, book)
    next_fields = study_form(page.text, chunks[1]["chunk_id"])
    forged = {**next_fields, "part_id": chunks[2]["chunk_id"]}
    assert client.post("/web/coach/message", data=forged).status_code == 403
    assert calls == []
    choose(client, book, 3)
    assert client.post("/web/coach/message", data=next_fields).status_code == 200
    assert calls[0]["sources"][0]["locator"] == "片段 2"
    assert repo.topic_part(user.user_id)["chunk_id"] == chunks[1]["chunk_id"]


def test_stale_edit_preserves_input_and_requires_reconfirmation(setup):
    _, client, repo, _, user, _, book, calls = setup
    path, fields = new_unit(client, book)
    client.post(path, data=fields)
    old = Forms(client.get(path).text).values(path)
    assert (
        client.post(
            path,
            data={**old, "title": "另一页面的新名称", "start_pos": "1", "end_pos": "1"},
        ).status_code
        == 200
    )
    stale = client.post(
        path, data={**old, "title": "保留我的文字", "start_pos": "2", "end_pos": "3"}
    )
    assert stale.status_code == 409 and "另一页面的新名称" in stale.text
    retry = Forms(stale.text).values(path)
    assert retry["title"] == "保留我的文字" and retry["revision"] == "2"
    assert client.post(path, data=retry).status_code == 200
    assert repo.book_units(user.user_id, book)[0]["title"] == "保留我的文字"
    assert calls == []


@pytest.mark.parametrize(
    "bad",
    [
        "bounds",
        "reverse",
        "blank",
        "long",
        "csrf",
        "origin",
        "extra",
        "unit",
        "duplicate",
    ],
)
def test_invalid_directory_changes_preserve_learning_state(setup, bad):
    _, client, repo, _, user, _, book, calls = setup
    path, fields = new_unit(client, book)
    headers = {}
    if bad == "bounds":
        fields["end_pos"] = "999"
    elif bad == "reverse":
        fields.update(start_pos="2", end_pos="1")
    elif bad == "blank":
        fields["title"] = " "
    elif bad == "long":
        fields["title"] = "字" * 81
    elif bad == "csrf":
        fields["csrf"] = "0" * 64
    elif bad == "origin":
        headers["origin"] = "https://evil.example"
    elif bad == "extra":
        fields["owner"] = user.user_id
    elif bad == "unit":
        path = path.rsplit("/", 1)[0] + "/" + uuid4().hex
    if bad == "duplicate":
        from urllib.parse import urlencode

        result = client.post(
            path,
            content=urlencode(fields) + "&title=other",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    else:
        result = client.post(path, data=fields, headers=headers)
    assert result.status_code in {400, 403}
    assert repo.book_units(user.user_id, book) == []
    assert repo.book_position(user.user_id, book) is None
    assert calls == []


def test_ownership_overlap_and_busy_guards(setup):
    _, client, repo, _, user, _, book, calls = setup
    path, fields = new_unit(client, book)
    assert client.post(path, data=fields).status_code == 200
    path2, fields2 = new_unit(client, book, start="2", end="3")
    assert client.post(path2, data=fields2).status_code == 400
    repo.claim(user.user_id, secrets.token_urlsafe(32), "pending", now=99999999999)
    assert client.post(path2, data={**fields2, "start_pos": "3"}).status_code == 409
    assert len(repo.book_units(user.user_id, book)) == 1
    assert calls == []
    client.cookies.clear()
    login(client, "two@example.com")
    assert client.get(f"/web/materials/{book}/plan").status_code == 404
    assert client.get(path).status_code == 404
    assert client.post(path, data=fields).status_code == 403


def test_pdf_blank_range_rejected_and_actual_page_range_kept(setup):
    _, client, repo, materials, user, _, _, calls = setup
    pdf = materials.add(
        user.user_id, "book.pdf", pdf_with_blank_middle(), title="文件页码"
    )
    path, fields = new_unit(client, pdf, start="2", end="2")
    rejected = client.post(path, data=fields)
    assert rejected.status_code == 400 and "没有可提取文字" in rejected.text
    assert client.post(path, data={**fields, "end_pos": "3"}).status_code == 200
    directory = client.get(f"/web/materials/{pdf}/plan")
    assert "PDF 第 2–3 页" in directory.text and "已讲解 0 / 1 段" in directory.text
    assert calls == [] and repo.book_position(user.user_id, pdf) is None


def test_same_origin_opaque_form_allowed_but_cross_site_rejected(setup):
    _, client, _, _, _, _, book, _ = setup
    path, fields = new_unit(client, book)
    assert (
        client.post(
            path,
            data=fields,
            headers={"origin": "null", "sec-fetch-site": "cross-site"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path,
            data=fields,
            headers={"origin": "null", "sec-fetch-site": "same-origin"},
        ).status_code
        == 200
    )
