"""一覧の記事を前回の状態と比べ、URL を貼る記事を決める。"""

from dataclasses import dataclass, field

NEW = "new"
UPDATED = "updated"


class NotifyError(Exception):
    """通知を送れなかった。その記事は記録せず、次回もう一度送る。"""


@dataclass(frozen=True)
class Change:
    kind: str
    entry: object


@dataclass
class RunResult:
    baseline: int = 0
    suppressed: int = 0
    posted: list = field(default_factory=list)
    failures: list = field(default_factory=list)


def find_changes(articles, entries):
    """新しい記事と版（rev）が変わった記事を、古い順に返す。"""
    changes = []
    seen = set()
    # 公開日時が同じなら一覧の下（古い方）を先にする
    for entry in sorted(reversed(entries), key=lambda entry: entry.published_at):
        if entry.content_id in seen:
            continue
        seen.add(entry.content_id)
        saved = articles.get(entry.content_id)
        if saved is None:
            changes.append(Change(NEW, entry))
        elif saved.get("rev") != entry.rev:
            changes.append(Change(UPDATED, entry))
    return changes


def run(state, entries, *, notify, save, max_changes=5):
    """notify(url) で URL を送り、送れた記事だけ記録して save() で保存する。"""
    articles = state["articles"]
    result = RunResult()

    if not articles:
        for entry in entries:
            _record(articles, entry)
        result.baseline = len(articles)
        save()
        return result

    changes = find_changes(articles, entries)
    if len(changes) > max_changes:
        for change in changes:
            _record(articles, change.entry)
        result.suppressed = len(changes)
        result.failures.append(
            "変化した記事が {} 件あり、上限の {} 件を超えたので URL を貼らずに記録しました。"
            "記事 ID の形が変わった可能性があります".format(len(changes), max_changes)
        )
        save()
        return result

    for change in changes:
        try:
            notify(change.entry.url)
        except NotifyError as error:
            # 順番が入れ替わらないよう、残りも次回に回す
            result.failures.append("{}: {}".format(change.entry.title, error))
            break
        _record(articles, change.entry)
        save()
        result.posted.append(change)
    return result


def _record(articles, entry):
    articles[entry.content_id] = {
        "title": entry.title,
        "url": entry.url,
        "publishedAt": entry.published_at,
        "rev": entry.rev,
    }
