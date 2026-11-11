"""leagueoflegends.com のパッチノート一覧ページを取得し、記事ごとの値を取り出す。

ページは Next.js で作られていて、表示に使うデータが <script id="__NEXT_DATA__"> に JSON で入っている。
見た目の HTML ではなくこの JSON を読むので、デザインが変わっても壊れにくい。
"""

import gzip
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin

from . import USER_AGENT

SITE = "https://www.leagueoflegends.com"
LIST_URL = SITE + "/ja-jp/news/tags/patch-notes/"
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class ScrapeError(Exception):
    """ページの構造が想定と違う。Riot 側のサイトが変わった可能性が高い。"""


@dataclass(frozen=True)
class ListEntry:
    content_id: str
    rev: str
    title: str
    url: str
    published_at: str


def fetch_text(url, *, opener=urllib.request.urlopen, sleep=time.sleep, attempts=3):
    """ページを gzip で取得する。5xx・429・通信エラーは少し待ってやり直し、それ以外の 4xx はすぐ諦める。"""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja", "Accept-Encoding": "gzip"}
    )
    for attempt in range(attempts):
        try:
            with opener(request, timeout=20) as response:
                body = response.read()
                if (response.headers.get("Content-Encoding") or "").lower() == "gzip":
                    body = gzip.decompress(body)
                return body.decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code < 500 and error.code != 429:
                raise
            last_error = error
        except OSError as error:
            last_error = error
        if attempt + 1 < attempts:
            sleep(5 * (attempt + 1))
    raise last_error


def parse_list(html):
    """一覧ページの記事を、ページに出ている順（新しい順）で返す。

    使うのは最新の 1 件だけだが、ページの形が変わったことに早く気づけるよう、全件を確かめる。
    """
    match = _NEXT_DATA.search(html)
    if not match:
        raise ScrapeError("__NEXT_DATA__ が見つかりません")
    try:
        blades = json.loads(match.group(1))["props"]["pageProps"]["page"]["blades"]
    except (ValueError, KeyError, TypeError) as error:
        raise ScrapeError("__NEXT_DATA__ の形が想定と違います: {!r}".format(error)) from error

    grid = next((blade for blade in blades if isinstance(blade, dict) and blade.get("type") == "articleCardGrid"), None)
    if grid is None:
        raise ScrapeError("ページに記事の一覧（articleCardGrid）がありません")

    entries = []
    for index, item in enumerate(grid.get("items") or []):
        try:
            analytics = item["analytics"]
            entries.append(
                ListEntry(
                    content_id=analytics["contentId"],
                    rev=analytics["rev"],
                    title=item["title"].strip(),
                    url=urljoin(SITE, item["action"]["payload"]["url"]),
                    published_at=item.get("publishedAt") or analytics.get("publishDate") or "",
                )
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise ScrapeError("一覧の {} 件目の形が想定と違います: {!r}".format(index + 1, error)) from error
    if not entries:
        raise ScrapeError("一覧に記事が 1 件もありません")
    return entries
