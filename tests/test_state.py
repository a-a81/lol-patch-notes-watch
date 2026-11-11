import pytest

from patchwatch.state import empty_state, load_state, save_state

LATEST = {
    "contentId": "patchNote.22.ja-jp",
    "title": "パッチノート 26.22",
    "url": "https://www.leagueoflegends.com/ja-jp/news/game-updates/patch-26-22-notes",
    "publishedAt": "2026-11-03T19:00:00.000Z",
    "rev": "r1",
}


def test_missing_file_is_an_empty_state(tmp_path):
    assert load_state(tmp_path / "state.json") == empty_state()


def test_round_trip(tmp_path):
    path = tmp_path / "nested" / "state.json"
    state = empty_state()
    state["latest"] = dict(LATEST)

    save_state(path, state)

    assert load_state(path) == state
    assert "パッチノート 26.22" in path.read_text(encoding="utf-8")
    assert not (tmp_path / "nested" / "state.json.tmp").exists()


def test_saving_the_same_state_twice_gives_the_same_bytes(tmp_path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["latest"] = dict(LATEST)

    save_state(path, state)
    first = path.read_bytes()
    save_state(path, load_state(path))

    assert path.read_bytes() == first
    assert b"\r\n" not in first


def test_other_schema_version_is_rejected(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"schemaVersion": 2, "latest": null}', encoding="utf-8")

    with pytest.raises(ValueError, match="schemaVersion"):
        load_state(path)
