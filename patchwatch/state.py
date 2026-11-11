"""前回の状態（記事ごとの版）を JSON ファイルで読み書きする。"""

import json
import os
from pathlib import Path

SCHEMA_VERSION = 1


def empty_state():
    return {"schemaVersion": SCHEMA_VERSION, "articles": {}}


def load_state(path):
    path = Path(path)
    if not path.exists():
        return empty_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("状態ファイルの schemaVersion が {} ではありません: {}".format(SCHEMA_VERSION, path))
    state.setdefault("articles", {})
    return state


def save_state(path, state):
    """一時ファイルに書いてから置き換える。途中で落ちても前回のファイルが残る。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    articles = sorted(state["articles"].items(), key=lambda item: item[1].get("publishedAt", ""), reverse=True)
    ordered = {"schemaVersion": state["schemaVersion"], "articles": dict(articles)}
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(ordered, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
