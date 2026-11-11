import pytest

from patchwatch.state import empty_state
from patchwatch.watcher import NEW, UPDATED, NotifyError, latest_entry, run
from pages import entry


class Discord:
    def __init__(self, fail=False):
        self.posted = []
        self.fail = fail

    def __call__(self, url):
        if self.fail:
            raise NotifyError("Discord が 500 を返しました（3 回試しました）")
        self.posted.append(url)


def watch(state, entries, discord=None):
    discord = discord or Discord()
    saves = []
    result = run(state, entries, notify=discord, save=lambda: saves.append(True))
    return result, discord, saves


def state_with(latest):
    state = empty_state()
    run(state, [latest], notify=lambda url: pytest.fail("初回は送らない"), save=lambda: None)
    return state


def test_first_run_records_the_latest_without_posting():
    state = empty_state()

    result, discord, saves = watch(state, [entry(22), entry(21)])

    assert result.baseline == entry(22)
    assert discord.posted == []
    assert saves
    assert state["latest"] == {
        "contentId": "patchNote.22.ja-jp",
        "title": "パッチノート 26.22",
        "url": "https://www.leagueoflegends.com/ja-jp/news/game-updates/patch-26-22-notes",
        "publishedAt": entry(22).published_at,
        "rev": "r1",
    }


def test_nothing_changed_posts_and_saves_nothing():
    state = state_with(entry(22))

    result, discord, saves = watch(state, [entry(22), entry(21)])

    assert discord.posted == []
    assert result.posted is None
    assert saves == []


def test_new_article_is_posted_and_recorded():
    state = state_with(entry(22))

    result, discord, saves = watch(state, [entry(23), entry(22)])

    assert discord.posted == [entry(23).url]
    assert result.posted.kind == NEW
    assert state["latest"]["contentId"] == "patchNote.23.ja-jp"
    assert saves


def test_updated_latest_article_is_posted():
    state = state_with(entry(22))

    result, discord, _ = watch(state, [entry(22, rev="r2"), entry(21)])

    assert discord.posted == [entry(22).url]
    assert result.posted.kind == UPDATED
    assert state["latest"]["rev"] == "r2"


def test_older_articles_are_ignored_even_if_they_change():
    state = state_with(entry(22))

    _, discord, _ = watch(state, [entry(22), entry(21, rev="r2"), entry(20, rev="r9")])

    assert discord.posted == []


def test_failed_post_is_retried_next_time():
    state = state_with(entry(22))

    result, _, saves = watch(state, [entry(23), entry(22)], Discord(fail=True))

    assert "パッチノート 26.23" in result.failures[0]
    assert state["latest"]["contentId"] == "patchNote.22.ja-jp"
    assert saves == []

    result, discord, _ = watch(state, [entry(23), entry(22)])

    assert discord.posted == [entry(23).url]
    assert result.failures == []


def test_removed_latest_article_does_not_post_the_older_one():
    state = state_with(entry(23))

    result, discord, saves = watch(state, [entry(22), entry(21)])

    assert discord.posted == []
    assert "パッチノート 26.23" in result.skipped
    assert result.failures == []
    assert state["latest"]["contentId"] == "patchNote.23.ja-jp"
    assert saves == []


def test_latest_entry_uses_publish_date_not_page_order():
    assert latest_entry([entry(21), entry(23), entry(22)]) == entry(23)
