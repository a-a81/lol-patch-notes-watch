"""パッチノート一覧を確認し、新しい記事と更新された記事の URL を Discord に貼る。

例:
  python -m patchwatch --dry-run             送らずに、貼る URL をログに出す（状態も保存しない）
  python -m patchwatch --send-latest         最新の記事の URL を 1 件送り、Webhook の設定を確かめる
  python -m patchwatch --state state/state.json

Webhook の URL は環境変数 DISCORD_WEBHOOK_URL に入れる。
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from .discord import is_webhook_url, post_message
from .riot import LIST_URL, ScrapeError, fetch_text, parse_list
from .state import load_state, save_state
from .watcher import NEW, UPDATED, NotifyError, run

log = logging.getLogger("patchwatch")
KIND_LABELS = {NEW: "新着", UPDATED: "更新"}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m patchwatch", description=__doc__.splitlines()[0])
    parser.add_argument("--state", default="state/state.json", help="状態ファイルの場所")
    parser.add_argument("--max-changes", type=int, default=5, help="1 回に貼る URL の上限")
    parser.add_argument("--dry-run", action="store_true", help="送らずに貼る URL をログに出す。状態も保存しない")
    parser.add_argument("--send-latest", action="store_true", help="最新の記事の URL を 1 件送って終わる")
    parser.add_argument("--commit-message-file", help="state ブランチの commit メッセージを書き出すファイル")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    summary = Summary(os.environ.get("GITHUB_STEP_SUMMARY"))

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not args.dry_run:
        if not webhook_url:
            log.error("環境変数 DISCORD_WEBHOOK_URL が設定されていません")
            return 2
        if not is_webhook_url(webhook_url):
            log.error("DISCORD_WEBHOOK_URL が Discord の Webhook の URL ではありません")
            return 2

    def notify(url):
        if args.dry_run:
            log.info("貼る URL（dry-run）: %s", url)
        else:
            post_message(webhook_url, url)

    state_path = Path(args.state)
    try:
        state = load_state(state_path)
    except (OSError, ValueError) as error:
        log.error("状態ファイルを読めませんでした: %s", error)
        summary.write("状態ファイルを読めませんでした: {}".format(error))
        return 1

    try:
        entries = parse_list(fetch_text(LIST_URL))
    except (ScrapeError, OSError) as error:
        log.error("一覧ページを読めませんでした: %s", error)
        summary.write("一覧ページを読めませんでした: {}".format(error))
        return 1
    log.info("一覧の記事: %d 件", len(entries))

    if args.send_latest:
        latest = max(entries, key=lambda entry: entry.published_at)
        try:
            notify(latest.url)
        except NotifyError as error:
            log.error("送れませんでした: %s", error)
            return 1
        log.info("最新の記事を送りました: %s", latest.title)
        return 0

    save = (lambda: None) if args.dry_run else (lambda: save_state(state_path, state))
    result = run(state, entries, notify=notify, save=save, max_changes=args.max_changes)

    report(result, len(entries), summary, posted_label="dry-run で貼る予定" if args.dry_run else "貼りました")
    if args.commit_message_file:
        message = commit_message(result)
        if message:
            Path(args.commit_message_file).write_text(message + "\n", encoding="utf-8")
    return 1 if result.failures else 0


def report(result, entry_count, summary, posted_label):
    lines = ["## パッチノートの確認", "", "- 一覧の記事: {} 件".format(entry_count)]
    if result.baseline:
        log.info("初回なので %d 件を通知せずに記録しました", result.baseline)
        lines.append("- 初回なので {} 件を通知せずに記録しました".format(result.baseline))
    for change in result.posted:
        kind = KIND_LABELS[change.kind]
        log.info("%s（%s）: %s %s", posted_label, kind, change.entry.title, change.entry.url)
        lines.append("- {}（{}）: [{}]({})".format(posted_label, kind, change.entry.title, change.entry.url))
    for failure in result.failures:
        log.error("失敗: %s", failure)
        lines.append("- 失敗: {}".format(failure))
    if not (result.baseline or result.posted or result.failures):
        log.info("変化はありませんでした")
        lines.append("- 変化はありませんでした")
    summary.write("\n".join(lines))


def commit_message(result):
    if result.baseline:
        return "Baseline {} articles".format(result.baseline)
    if result.suppressed:
        return "Record {} changes without posting".format(result.suppressed)
    lines = ["{}: {}".format("New" if change.kind == NEW else "Updated", change.entry.title) for change in result.posted]
    if len(lines) > 1:
        return "Post {} articles\n\n".format(len(lines)) + "\n".join(lines)
    return lines[0] if lines else ""


class Summary:
    """GitHub Actions の実行画面に出す Summary。Actions の外では何もしない。"""

    def __init__(self, path):
        self.path = path

    def write(self, text):
        if self.path:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
