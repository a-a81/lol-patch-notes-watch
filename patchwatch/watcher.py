"""一覧の最新の記事を前回と比べ、URL を貼るかを決める。"""

from dataclasses import dataclass, field

NEW = "new"
UPDATED = "updated"


class NotifyError(Exception):
    """通知を送れなかった。状態は更新せず、次回もう一度送る。"""


@dataclass(frozen=True)
class Change:
    kind: str
    entry: object


@dataclass
class RunResult:
    baseline: object = None
    posted: object = None
    skipped: str = ""
    failures: list = field(default_factory=list)


def latest_entry(entries):
    """公開日時が一番新しい記事。同じなら一覧で上にある方。"""
    return max(entries, key=lambda entry: entry.published_at)


def run(state, entries, *, notify, save):
    """notify(url) で URL を送り、送れたときだけ記録して save() で保存する。"""
    latest = latest_entry(entries)
    saved = state.get("latest")
    result = RunResult()

    if saved is None:
        state["latest"] = _record(latest)
        save()
        result.baseline = latest
        return result

    if saved["contentId"] != latest.content_id:
        if latest.published_at < saved["publishedAt"]:
            # 最新の記事が一覧から消えた。古い記事を新着として貼らない
            result.skipped = "前回の最新記事（{}）が一覧にないので、何もしませんでした".format(saved["title"])
            return result
        kind = NEW
    elif saved["rev"] != latest.rev:
        kind = UPDATED
    else:
        return result

    try:
        notify(latest.url)
    except NotifyError as error:
        result.failures.append("{}: {}".format(latest.title, error))
        return result
    state["latest"] = _record(latest)
    save()
    result.posted = Change(kind, latest)
    return result


def _record(entry):
    return {
        "contentId": entry.content_id,
        "title": entry.title,
        "url": entry.url,
        "publishedAt": entry.published_at,
        "rev": entry.rev,
    }
