from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from coach.conversation_dates import conversation_date_window
from tests import test_web_conversation_review as base
from tests.test_conversation_review import turn, topic
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_paid_services = base.no_paid_services
no_plain_smtp = base.no_plain_smtp


def test_combined_dates_paging_detail_neighbors_and_clear_keep_state(setup):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    lower, upper = conversation_date_window("2024-02-29", "2024-02-29")
    a = topic(repo, "历史主题", user=user.user_id)
    oldest = turn(repo, "关键词：范围之前", user=user.user_id, now=lower - 2)
    for n in range(22):
        turn(repo, "关键词" + str(n), user=user.user_id, now=lower + n * 2)
    turn(repo, "关键词：范围之后", user=user.user_id, now=upper)
    current = topic(repo, "当前主题", user=user.user_id, now=upper + 2)
    before = {p: p.read_bytes() for p in [repo.database_path, materials.database_path]}
    params = {"q": "关键词", "topic": a, "start": "2024-02-29", "end": "2024-02-29"}
    first = client.get("/web/conversations", params=params)
    assert first.status_code == 200 and len(base.records(first.text)) == 20
    assert "范围之前" not in first.text and "范围之后" not in first.text
    assert 'type="date" name="start" value="2024-02-29"' in first.text
    next_link = next(
        x
        for x in Links(first.text).links
        if x.startswith("/web/conversations?") and "page=2" in x
    )
    second = client.get(next_link)
    assert len(base.records(second.text)) == 2
    detail = client.get(base.records(second.text)[-1])
    back = next(
        x for x in Links(detail.text).links if x.startswith("/web/conversations?")
    )
    assert parse_qs(urlsplit(back).query) == {
        k: [v] for k, v in {**params, "page": "2"}.items()
    }
    previous = next(
        x
        for x in Links(detail.text).links
        if x.startswith(f"/web/conversations/{oldest}?")
    )
    outside = client.get(previous)
    assert "本轮发起日期不在所选范围内" in outside.text
    # Choose the explicit clear URL by its empty date parameters.
    clear = next(x for x in Links(second.text).links if "start=&end=" in x)
    values = parse_qs(urlsplit(clear).query, keep_blank_values=True)
    assert (
        values["q"] == ["关键词"]
        and values["topic"] == [a]
        and values["start"] == values["end"] == [""]
    )
    assert client.get(clear).status_code == 200
    assert repo.active_topic(user.user_id)["topic_id"] == current and calls == []
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize(
    "query",
    [
        "start=2024-02-30",
        "end=2024-13-01",
        "start=2024-03-01&end=2024-02-29",
        "start=2024-02-29&start=2024-02-28",
        "end=2024-02-29&end=2024-03-01",
        "start=%3Cimg%20src=x%3E",
        "start=2024-2-29",
    ],
)
def test_invalid_ranges_rejected_on_list_and_detail(setup, query):
    _, client, repo, _, user, _, _ = setup
    login(client)
    identity = turn(repo, "私有问题", user=user.user_id)
    for path in ["/web/conversations", f"/web/conversations/{identity}"]:
        response = client.get(path + "?" + query)
        assert response.status_code == 400 and "<img src=x>" not in response.text


def test_other_accounts_cannot_find_private_records_with_dates(setup):
    app, client, repo, _, user, _, _ = setup
    login(client)
    lower, _ = conversation_date_window("2024-02-29", "")
    identity = turn(repo, "PRIVATE_DATE_RECORD", user=user.user_id, now=lower)
    with TestClient(app, base_url=BASE) as other:
        assert (
            other.get(
                "/web/conversations?start=2024-02-29", follow_redirects=False
            ).status_code
            == 303
        )
        login(other, "two@example.com")
        response = other.get("/web/conversations?start=2024-02-29&end=2024-02-29")
        assert (
            response.status_code == 200 and "PRIVATE_DATE_RECORD" not in response.text
        )
        assert (
            other.get(f"/web/conversations/{identity}?start=2024-02-29").status_code
            == 404
        )


def test_open_ended_range_and_no_date_default_remain_compatible(setup):
    _, client, repo, _, user, _, _ = setup
    login(client)
    lower, _ = conversation_date_window("2024-02-29", "")
    a = turn(repo, "之前的内容", user=user.user_id, now=lower - 2)
    b = turn(repo, "当天的内容", user=user.user_id, now=lower)
    after = client.get("/web/conversations?start=2024-02-29")
    before = client.get("/web/conversations?end=2024-02-28")
    assert len(base.records(after.text)) == len(base.records(before.text)) == 1
    assert (
        f"/web/conversations/{b}?" in after.text
        and f"/web/conversations/{a}?" in before.text
    )
    assert len(base.records(client.get("/web/conversations").text)) == 2
