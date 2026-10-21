"""Reader page navigation works through GET forms without a JS engine."""

from html.parser import HTMLParser

import pytest

from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from tests.test_web_book_reader import image_book
from tests.test_web_coach_dialogue import login
from tests.test_web_library import (
    setup as setup,
    no_real_services as no_real_services,
    password_hash as password_hash,
)


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = {}
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = attrs.get("id")
            self.forms[self.current] = {"attrs": attrs, "values": {}, "buttons": []}
        elif self.current and tag == "input" and attrs.get("name"):
            self.forms[self.current]["values"][attrs["name"]] = attrs.get("value", "")
        elif self.current and tag == "button":
            self.forms[self.current]["buttons"].append(attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


@pytest.mark.parametrize("kind", ["pdf", "txt"])
def test_navigation_roundtrip_without_js_and_no_learning_writes(setup, kind):
    _, client, user, calls, directory = setup
    login(client)
    repo = MaterialRepository(directory / "coach_library.db")
    raw = (
        image_book() if kind == "pdf" else ("连续阅读，不改学习位置。\n" * 600).encode()
    )
    identity = repo.add(user.user_id, "reading." + kind, raw)
    coach = CoachRepository(directory / "coach_conversations.db")
    coach.create_topic(user.user_id, "保持原主题", identity)
    before = {p: p.read_bytes() for p in (repo.database_path, coach.database_path)}
    path = f"/web/materials/{identity}/read"
    first = client.get(path)
    forms = Forms(first.text).forms
    prev, nxt = forms["reader-previous-form"], forms["reader-next-form"]
    assert "disabled" in prev["buttons"][0]
    assert prev["buttons"][0]["title"] == "已到第一页"
    assert "disabled" not in nxt["buttons"][0]
    assert nxt["attrs"]["method"] == "get" and nxt["values"] == {"page": "2"}
    second = client.get(path, params=nxt["values"])
    assert second.status_code == 200 and 'data-initial="2"' in second.text
    second_forms = Forms(second.text).forms
    assert all(
        "disabled" not in second_forms[name]["buttons"][0]
        for name in ("reader-previous-form", "reader-next-form")
    )
    back = client.get(path, params=second_forms["reader-previous-form"]["values"])
    assert back.status_code == 200 and 'data-initial="1"' in back.text
    assert "Enter 到下一页" in first.text
    assert 'aria-describedby="reader-shortcuts"' in first.text
    assert all(p.read_bytes() == value for p, value in before.items()) and calls == []


def test_last_page_and_single_page_boundaries_are_explicit(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo = MaterialRepository(directory / "coach_library.db")
    for pages in (1, 12):
        identity = repo.add(user.user_id, "book.pdf", image_book(pages))
        response = client.get(f"/web/materials/{identity}/read?page={pages}")
        forms = Forms(response.text).forms
        last = forms["reader-next-form"]
        assert "disabled" in last["buttons"][0]
        assert last["buttons"][0]["title"] == "已到最后一页"
        assert last["values"]["page"] == str(pages)
        assert ("disabled" in forms["reader-previous-form"]["buttons"][0]) == (
            pages == 1
        )
    assert calls == []
