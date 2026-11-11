import pytest

from patchwatch.state import empty_state
from patchwatch.watcher import NEW, UPDATED, NotifyError, find_changes, run
from pages import entry


class Discord:
    def __init__(self, fail_on=()):
        self.posted = []
        self.fail_on = set(fail_on)

    def __call__(self, url):
        if url in self.fail_on:
            raise NotifyError("Discord が 500 を返しました（3 回試しました）")
        self.posted.append(url)


def watch(state, entries, discord=None, **options):
    discord = discord or Discord()
    saves = []
    result = run(state, entries, notify=discord, save=lambda: saves.append(True), **options)
    return result, discord, saves


def state_with(*entries):
    state = empty_state()
    run(state, list(entries), notify=lambda url: pytest.fail("初回は送らない"), save=lambda: None)
    return state


def test_first_run_records_everything_without_posting():
    state = empty_state()
    entries = [entry(22), entry(21), entry(20)]

    result, discord, saves = watch(state, entries)

    assert result.baseline == 3
    assert discord.posted == []
    assert result.failures == []
    assert saves
    assert state["articles"]["patchNote.22.ja-jp"] == {
        "title": "パッチノート 26.22",
        "url": "https://www.leagueoflegends.com/ja-jp/news/game-updates/patch-26-22-notes",
        "publishedAt": entry(22).published_at,
        "rev": "r1",
    }


def test_nothing_changed_posts_nothing_and_saves_nothing():
    state = state_with(entry(22), entry(21))

    result, discord, saves = watch(state, [entry(22), entry(21)])

    assert discord.posted == []
    assert result.posted == []
    assert saves == []


def test_new_article_is_posted_and_recorded():
    state = state_with(entry(21), entry(20))

    result, discord, _ = watch(state, [entry(22), entry(21), entry(20)])

    assert discord.posted == [entry(22).url]
    assert [change.kind for change in result.posted] == [NEW]
    assert state["articles"]["patchNote.22.ja-jp"]["rev"] == "r1"


def test_updated_article_is_posted_when_rev_changes():
    state = state_with(entry(22), entry(21))

    result, discord, _ = watch(state, [entry(22, rev="r2"), entry(21)])

    assert discord.posted == [entry(22).url]
    assert [change.kind for change in result.posted] == [UPDATED]
    assert state["articles"]["patchNote.22.ja-jp"]["rev"] == "r2"


def test_changes_are_posted_oldest_first():
    state = state_with(entry(20))

    _, discord, _ = watch(state, [entry(23), entry(22), entry(21, rev="r2"), entry(20, rev="r2")])

    assert discord.posted == [entry(20).url, entry(21).url, entry(22).url, entry(23).url]


def test_failed_post_is_retried_next_time_and_keeps_order():
    state = state_with(entry(20))
    entries = [entry(22), entry(21), entry(20)]

    result, discord, _ = watch(state, entries, Discord(fail_on={entry(21).url}))

    assert discord.posted == []
    assert len(result.failures) == 1
    assert "パッチノート 26.21" in result.failures[0]
    assert "patchNote.21.ja-jp" not in state["articles"]
    assert "patchNote.22.ja-jp" not in state["articles"]

    result, discord, _ = watch(state, entries)

    assert discord.posted == [entry(21).url, entry(22).url]
    assert result.failures == []


def test_each_successful_post_is_saved_right_away():
    state = state_with(entry(20))

    _, _, saves = watch(state, [entry(22), entry(21), entry(20)])

    assert len(saves) == 2


def test_too_many_changes_are_recorded_without_posting():
    state = state_with(entry(20))
    entries = [entry(number) for number in range(26, 19, -1)]

    result, discord, _ = watch(state, entries, max_changes=5)

    assert discord.posted == []
    assert result.suppressed == 6
    assert "上限の 5 件" in result.failures[0]
    assert len(state["articles"]) == 7


def test_article_that_left_the_list_is_kept():
    state = state_with(entry(22), entry(21))

    _, discord, _ = watch(state, [entry(22)])

    assert discord.posted == []
    assert "patchNote.21.ja-jp" in state["articles"]


def test_find_changes_ignores_duplicates_in_the_list():
    changes = find_changes({}, [entry(22), entry(22)])
    assert [change.entry for change in changes] == [entry(22)]
