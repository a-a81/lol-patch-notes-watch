import json

import pytest

from patchwatch.state import empty_state, load_state, save_state


def test_missing_file_is_an_empty_state(tmp_path):
    assert load_state(tmp_path / "state.json") == empty_state()


def test_round_trip_sorts_articles_newest_first(tmp_path):
    path = tmp_path / "nested" / "state.json"
    state = empty_state()
    state["articles"]["old"] = {"title": "パッチノート 26.21", "url": "u1", "publishedAt": "2026-10-20T18:00:00.000Z", "rev": "a"}
    state["articles"]["new"] = {"title": "パッチノート 26.22", "url": "u2", "publishedAt": "2026-11-03T19:00:00.000Z", "rev": "b"}

    save_state(path, state)

    assert load_state(path) == state
    assert list(json.loads(path.read_text(encoding="utf-8"))["articles"]) == ["new", "old"]
    assert "パッチノート" in path.read_text(encoding="utf-8")
    assert not (tmp_path / "nested" / "state.json.tmp").exists()


def test_saving_the_same_state_twice_gives_the_same_bytes(tmp_path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["articles"]["a"] = {"title": "t", "url": "u", "publishedAt": "p", "rev": "r"}

    save_state(path, state)
    first = path.read_bytes()
    save_state(path, load_state(path))

    assert path.read_bytes() == first
    assert b"\r\n" not in first


def test_other_schema_version_is_rejected(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"schemaVersion": 2, "articles": {}}', encoding="utf-8")

    with pytest.raises(ValueError, match="schemaVersion"):
        load_state(path)
