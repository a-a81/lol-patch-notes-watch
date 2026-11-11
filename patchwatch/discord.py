"""Discord の Webhook にメッセージを送る。

Webhook の URL を知っていれば誰でも投稿できるので、エラーやログに URL を出さない。
"""

import json
import time
import urllib.error
import urllib.request

from . import USER_AGENT
from .watcher import NotifyError

WEBHOOK_PREFIXES = ("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")
_MAX_WAIT_SECONDS = 60


def is_webhook_url(url):
    return url.startswith(WEBHOOK_PREFIXES)


def post_message(webhook_url, content, *, opener=urllib.request.urlopen, sleep=time.sleep, attempts=3):
    """429 は Discord が指定した秒数、5xx と通信エラーは少し待って、最大 attempts 回送る。"""
    payload = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode("utf-8")
    separator = "&" if "?" in webhook_url else "?"
    request = urllib.request.Request(
        webhook_url + separator + "wait=true",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    for attempt in range(attempts):
        try:
            with opener(request, timeout=15):
                return
        except urllib.error.HTTPError as error:
            if error.code == 429:
                wait = _retry_after(error)
            elif error.code >= 500:
                wait = 2 ** attempt
            else:
                raise NotifyError("Discord が {} を返しました: {}".format(error.code, _snippet(error))) from None
            last_problem = "Discord が {} を返しました".format(error.code)
        except OSError as error:
            wait = 2 ** attempt
            last_problem = "Discord に接続できませんでした: {}".format(getattr(error, "reason", error))
        if attempt + 1 < attempts:
            sleep(wait)
    raise NotifyError("{}（{} 回試しました）".format(last_problem, attempts))


def _retry_after(error):
    try:
        seconds = float(json.loads(error.read().decode("utf-8"))["retry_after"])
    except (ValueError, KeyError, TypeError, OSError):
        try:
            seconds = float(error.headers.get("Retry-After", 1))
        except (TypeError, ValueError, AttributeError):
            seconds = 1.0
    return min(max(seconds, 0.0), _MAX_WAIT_SECONDS)


def _snippet(error):
    try:
        return error.read().decode("utf-8", errors="replace")[:200]
    except OSError:
        return ""
