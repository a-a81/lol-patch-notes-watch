import gzip
import io
import urllib.error

import pytest

from patchwatch.riot import ListEntry, ScrapeError, fetch_text, parse_list
from pages import item, list_page


def test_parse_list_extracts_entries_in_page_order():
    html = list_page([
        item("patchNote.b.ja-jp", "rev-b", "リーグ・オブ・レジェンド パッチノート 26.22",
             "/ja-jp/news/game-updates/league-of-legends-patch-26-22-notes", "2026-11-03T19:00:00.000Z"),
        item("a.ja-jp", "rev-a", " パッチノート 26.21 ", "/ja-jp/news/game-updates/league-of-legends-patch-26-21-notes",
             "2026-10-20T18:00:00.000Z"),
    ])

    assert parse_list(html) == [
        ListEntry("patchNote.b.ja-jp", "rev-b", "リーグ・オブ・レジェンド パッチノート 26.22",
                  "https://www.leagueoflegends.com/ja-jp/news/game-updates/league-of-legends-patch-26-22-notes",
                  "2026-11-03T19:00:00.000Z"),
        ListEntry("a.ja-jp", "rev-a", "パッチノート 26.21",
                  "https://www.leagueoflegends.com/ja-jp/news/game-updates/league-of-legends-patch-26-21-notes",
                  "2026-10-20T18:00:00.000Z"),
    ]


def test_parse_list_keeps_absolute_urls():
    html = list_page([item("a", "r", path="https://www.leagueoflegends.com/ja-jp/news/game-updates/x")])
    assert parse_list(html)[0].url == "https://www.leagueoflegends.com/ja-jp/news/game-updates/x"


def test_parse_list_falls_back_to_analytics_publish_date():
    raw = item("a", "r", published="2026-11-03T19:00:00.000Z")
    del raw["publishedAt"]
    assert parse_list(list_page([raw]))[0].published_at == "2026-11-03T19:00:00.000Z"


@pytest.mark.parametrize(
    "html, message",
    [
        ("<html><body>メンテナンス中</body></html>", "__NEXT_DATA__"),
        ('<script id="__NEXT_DATA__">{"props": {}}</script>', "形が想定と違います"),
        (list_page([item("a", "r")], blade_type="somethingElse"), "articleCardGrid"),
        (list_page([]), "1 件もありません"),
    ],
)
def test_parse_list_rejects_unexpected_pages(html, message):
    with pytest.raises(ScrapeError, match=message):
        parse_list(html)


def test_parse_list_reports_which_item_is_broken():
    broken = item("b", "r")
    del broken["analytics"]["rev"]
    with pytest.raises(ScrapeError, match="2 件目"):
        parse_list(list_page([item("a", "r"), broken]))


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code):
    return urllib.error.HTTPError("https://example.com", code, "error", {}, io.BytesIO(b""))


def test_fetch_text_retries_server_errors():
    replies = [http_error(503), FakeResponse("一覧".encode("utf-8"))]
    waits = []

    def opener(request, timeout):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    assert fetch_text("https://example.com", opener=opener, sleep=waits.append) == "一覧"
    assert waits == [5]


def test_fetch_text_gives_up_on_not_found():
    def opener(request, timeout):
        raise http_error(404)

    with pytest.raises(urllib.error.HTTPError):
        fetch_text("https://example.com", opener=opener, sleep=lambda seconds: pytest.fail("待たずに諦める"))


def test_fetch_text_sends_user_agent_and_asks_for_gzip():
    sent = {}

    def opener(request, timeout):
        sent["agent"] = request.get_header("User-agent")
        sent["encoding"] = request.get_header("Accept-encoding")
        return FakeResponse(b"ok")

    assert fetch_text("https://example.com", opener=opener) == "ok"
    assert sent["agent"].startswith("lol-patch-notes-watch/")
    assert sent["encoding"] == "gzip"


def test_fetch_text_decompresses_gzip():
    body = gzip.compress("パッチノート一覧".encode("utf-8"))

    def opener(request, timeout):
        return FakeResponse(body, {"Content-Encoding": "gzip"})

    assert fetch_text("https://example.com", opener=opener) == "パッチノート一覧"
