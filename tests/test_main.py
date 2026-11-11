import json

import pytest

import patchwatch.__main__ as cli
from pages import item, list_page

PAGE_V1 = list_page([
    item("patchNote.22.ja-jp", "r1", "パッチノート 26.22", "/ja-jp/news/game-updates/patch-26-22-notes", "2026-11-03T19:00:00.000Z"),
    item("patchNote.21.ja-jp", "r1", "パッチノート 26.21", "/ja-jp/news/game-updates/patch-26-21-notes", "2026-10-20T18:00:00.000Z"),
])
PAGE_V2 = list_page([
    item("patchNote.23.ja-jp", "r1", "パッチノート 26.23", "/ja-jp/news/game-updates/patch-26-23-notes", "2026-11-17T19:00:00.000Z"),
    item("patchNote.22.ja-jp", "r2", "パッチノート 26.22", "/ja-jp/news/game-updates/patch-26-22-notes", "2026-11-03T19:00:00.000Z"),
    item("patchNote.21.ja-jp", "r1", "パッチノート 26.21", "/ja-jp/news/game-updates/patch-26-21-notes", "2026-10-20T18:00:00.000Z"),
])
WEBHOOK = "https://discord.com/api/webhooks/123/token"


@pytest.fixture
def site(monkeypatch):
    pages = {"current": PAGE_V1}
    posted = []
    monkeypatch.setattr(cli, "fetch_text", lambda url: pages["current"])
    monkeypatch.setattr(cli, "post_message", lambda webhook, content: posted.append(content))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", WEBHOOK)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return pages, posted


def test_baseline_then_post_changes(site, tmp_path):
    pages, posted = site
    state = tmp_path / "state.json"
    message = tmp_path / "message.txt"

    assert cli.main(["--state", str(state), "--commit-message-file", str(message)]) == 0
    assert posted == []
    assert message.read_text(encoding="utf-8") == "Baseline 2 articles\n"

    pages["current"] = PAGE_V2
    assert cli.main(["--state", str(state), "--commit-message-file", str(message)]) == 0
    assert posted == [
        "https://www.leagueoflegends.com/ja-jp/news/game-updates/patch-26-22-notes",
        "https://www.leagueoflegends.com/ja-jp/news/game-updates/patch-26-23-notes",
    ]
    assert message.read_text(encoding="utf-8") == (
        "Post 2 articles\n\nUpdated: パッチノート 26.22\nNew: パッチノート 26.23\n"
    )
    assert json.loads(state.read_text(encoding="utf-8"))["articles"]["patchNote.22.ja-jp"]["rev"] == "r2"


def test_dry_run_does_not_post_or_save(site, tmp_path, monkeypatch):
    pages, posted = site
    monkeypatch.delenv("DISCORD_WEBHOOK_URL")
    state = tmp_path / "state.json"

    assert cli.main(["--state", str(state), "--dry-run"]) == 0

    assert posted == []
    assert not state.exists()


def test_send_latest_posts_newest_url_without_touching_state(site, tmp_path):
    pages, posted = site
    pages["current"] = PAGE_V2
    state = tmp_path / "state.json"

    assert cli.main(["--state", str(state), "--send-latest"]) == 0

    assert posted == ["https://www.leagueoflegends.com/ja-jp/news/game-updates/patch-26-23-notes"]
    assert not state.exists()


@pytest.mark.parametrize("value", ["", "https://example.com/hook"])
def test_bad_webhook_setting_exits_with_2(site, tmp_path, monkeypatch, value):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", value)
    assert cli.main(["--state", str(tmp_path / "state.json")]) == 2


def test_broken_page_fails_and_writes_summary(site, tmp_path, monkeypatch):
    pages, _ = site
    pages["current"] = "<html>メンテナンス中</html>"
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    state = tmp_path / "state.json"

    assert cli.main(["--state", str(state)]) == 1

    assert "__NEXT_DATA__" in summary.read_text(encoding="utf-8")
    assert not state.exists()
