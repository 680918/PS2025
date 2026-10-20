from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from tests import test_web_studies as base
from tests import test_web_coach_dialogue as dialogue_tests
from tests.test_study_find import learning
from tests.test_web_coach_dialogue import Forms, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_paid_services = base.no_paid_services
no_external_services = dialogue_tests.no_external_services


class Cards(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.count = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "article" and "study-card" in dict(attrs).get("class", "").split():
            self.count += 1


def test_summary_results_paging_clear_and_open_are_read_only_until_explicit_action(
    setup,
):
    _, client, repo, materials, user, other, calls = setup
    login(client)
    ids = [
        learning(
            repo,
            f"阅读实践 {n:02d}",
            user=user.user_id,
            progress="复习 & 应用",
            now=100 + n,
        )
        for n in range(13)
    ]
    learning(repo, "其他人的隐私主题", user=other.user_id, progress="复习 & 应用")
    current = learning(repo, "当前学习保持原样", user=user.user_id, now=200)
    before = repo.database_path.read_bytes()
    first = client.get("/web/studies", params={"q": "复习 & 应用"})
    assert first.status_code == 200 and Cards(first.text).count == 10
    assert "匹配位置：已讨论" in first.text
    assert "其他人的隐私主题" not in first.text
    next_url = next(
        url
        for url in Links(first.text).links
        if parse_qs(urlsplit(url).query).get("page") == ["2"]
    )
    assert parse_qs(urlsplit(next_url).query)["q"] == ["复习 & 应用"]
    second = client.get(next_url)
    assert Cards(second.text).count == 3 and "阅读实践 00" in second.text
    previous = next(
        url
        for url in Links(second.text).links
        if parse_qs(urlsplit(url).query).get("page") == ["1"]
    )
    assert parse_qs(urlsplit(previous).query)["q"] == ["复习 & 应用"]
    cleared = client.get("/web/studies")
    assert Cards(cleared.text).count == 10 and "当前学习保持原样" in cleared.text
    assert "匹配位置：" not in cleared.text
    assert repo.active_topic(user.user_id)["topic_id"] == current
    assert repo.database_path.read_bytes() == before and calls == []
    open_path = f"/web/studies/{ids[0]}/open"
    opened = client.post(open_path, data=Forms(second.text).values(open_path))
    assert opened.status_code == 200
    assert repo.active_topic(user.user_id)["topic_id"] == ids[0] and calls == []


def test_all_match_labels_escaped_input_and_no_result_state(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    learning(
        repo,
        "API 学习",
        user=user.user_id,
        progress="使用 ＡＰＩ",
        next_step="复习 api",
    )
    page = client.get("/web/studies", params={"q": "Api"})
    assert page.status_code == 200 and "匹配位置：主题名称、已讨论、下一步" in page.text
    assert 'aria-describedby="study-search-help"' in page.text
    assert 'href="/web/studies">查看全部主题' in page.text
    malicious = '"><img src=x onerror=alert(1)>'
    learning(repo, "安全文字", user=user.user_id, progress=malicious)
    found = client.get("/web/studies", params={"q": malicious})
    assert Cards(found.text).count == 1
    assert "<img src=x" not in found.text and "&lt;img src=x" in found.text
    missing = client.get("/web/studies", params={"q": "不存在的学习摘要"})
    assert Cards(missing.text).count == 0 and "没有找到匹配的学习记录" in missing.text
    assert missing.headers["cache-control"] == "no-store" and calls == []


@pytest.mark.parametrize(
    "query",
    [
        "q=a&q=b",
        "page=1&page=2",
        "q=" + "x" * 121,
        "page=0",
        "page=-1",
        "page=999999",
        "page=abc",
    ],
)
def test_invalid_or_ambiguous_search_does_not_write_or_call_ai(setup, query):
    _, client, repo, _, _, _, calls = setup
    login(client)
    before = repo.database_path.read_bytes()
    response = client.get("/web/studies?" + query)
    assert (
        response.status_code == 400 and "请检查主题搜索文字和目录页码" in response.text
    )
    assert repo.database_path.read_bytes() == before and calls == []


def test_visitors_and_forged_user_query_cannot_read_other_accounts(setup):
    _, client, repo, _, user, other, calls = setup
    learning(repo, "只属于另一个人的标题", user=other.user_id, progress="秘密摘要")
    assert (
        client.get("/web/studies?q=秘密摘要", follow_redirects=False).status_code == 303
    )
    login(client)
    result = client.get(
        "/web/studies", params={"q": "秘密摘要", "user_id": other.user_id}
    )
    assert result.status_code == 200 and Cards(result.text).count == 0
    assert "只属于另一个人的标题" not in result.text and calls == []
