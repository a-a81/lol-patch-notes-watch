"""実際の一覧ページと同じ形（__NEXT_DATA__）の、テスト用の小さなページを作る。"""

import json

from patchwatch.riot import ListEntry


def item(content_id, rev, title="パッチノート 26.22", path="/ja-jp/news/game-updates/patch-26-22-notes",
         published="2026-11-03T19:00:00.000Z"):
    return {
        "title": title,
        "action": {"type": "weblink", "payload": {"url": path}},
        "analytics": {"contentId": content_id, "contentLocale": "ja-jp", "rev": rev, "publishDate": published},
        "publishedAt": published,
    }


def list_page(items, blade_type="articleCardGrid"):
    data = {"props": {"pageProps": {"page": {"blades": [{"type": "riotbar"}, {"type": blade_type, "items": items}]}}}}
    return (
        '<html><head><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script></head><body></body></html>"
    )


def entry(number, rev="r1"):
    """パッチ 26.<number> の記事。番号が大きいほど新しい。"""
    return ListEntry(
        content_id="patchNote.{}.ja-jp".format(number),
        rev=rev,
        title="パッチノート 26.{}".format(number),
        url="https://www.leagueoflegends.com/ja-jp/news/game-updates/patch-26-{}-notes".format(number),
        published_at="2026-11-{:02d}T19:00:00.000Z".format(number),
    )
