import io
import json
import urllib.error

import pytest

from patchwatch.discord import is_webhook_url, post_message
from patchwatch.watcher import NotifyError

WEBHOOK = "https://discord.com/api/webhooks/123/secret-token"
ARTICLE = "https://www.leagueoflegends.com/ja-jp/news/game-updates/league-of-legends-patch-26-22-notes"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, body=b"", headers=None):
    return urllib.error.HTTPError(WEBHOOK, code, "error", headers or {}, io.BytesIO(body))


class Opener:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_sends_only_the_url_without_mentions():
    opener = Opener(FakeResponse(b"{}"))

    post_message(WEBHOOK, ARTICLE, opener=opener)

    request = opener.requests[0]
    assert request.full_url == WEBHOOK + "?wait=true"
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"content": ARTICLE, "allowed_mentions": {"parse": []}}
    assert request.get_header("User-agent").startswith("lol-patch-notes-watch/")


def test_waits_as_discord_says_on_rate_limit():
    opener = Opener(http_error(429, b'{"retry_after": 1.5}'), FakeResponse(b"{}"))
    waits = []

    post_message(WEBHOOK, ARTICLE, opener=opener, sleep=waits.append)

    assert waits == [1.5]
    assert len(opener.requests) == 2


def test_gives_up_after_repeated_server_errors():
    opener = Opener(http_error(502), http_error(502), http_error(502))
    waits = []

    with pytest.raises(NotifyError, match="502.*3 回"):
        post_message(WEBHOOK, ARTICLE, opener=opener, sleep=waits.append)
    assert waits == [1, 2]


def test_client_error_fails_at_once_without_leaking_the_webhook_url():
    opener = Opener(http_error(404, b'{"message": "Unknown Webhook", "code": 10015}'))

    with pytest.raises(NotifyError) as caught:
        post_message(WEBHOOK, ARTICLE, opener=opener, sleep=lambda seconds: pytest.fail("待たずに諦める"))

    assert "Unknown Webhook" in str(caught.value)
    assert "secret-token" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_connection_error_message_does_not_leak_the_webhook_url():
    opener = Opener(*[urllib.error.URLError("timed out")] * 3)

    with pytest.raises(NotifyError) as caught:
        post_message(WEBHOOK, ARTICLE, opener=opener, sleep=lambda seconds: None)

    assert "timed out" in str(caught.value)
    assert "secret-token" not in str(caught.value)


@pytest.mark.parametrize(
    "url, expected",
    [
        (WEBHOOK, True),
        ("https://discordapp.com/api/webhooks/123/token", True),
        ("https://example.com/api/webhooks/123/token", False),
        ("http://discord.com/api/webhooks/123/token", False),
    ],
)
def test_is_webhook_url(url, expected):
    assert is_webhook_url(url) is expected
