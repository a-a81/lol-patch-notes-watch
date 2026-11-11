# LoL Patch Notes Watch

[![Watch patch notes](https://github.com/a-a81/lol-patch-notes-watch/actions/workflows/watch.yml/badge.svg)](https://github.com/a-a81/lol-patch-notes-watch/actions/workflows/watch.yml)
[![Test](https://github.com/a-a81/lol-patch-notes-watch/actions/workflows/test.yml/badge.svg)](https://github.com/a-a81/lol-patch-notes-watch/actions/workflows/test.yml)

League of Legends の[日本語パッチノート一覧](https://www.leagueoflegends.com/ja-jp/news/tags/patch-notes/)を 1 時間ごとに確認し、最新の記事が新しくなっていたり更新されていたりしたら、その URL を Discord に貼ります。何も変わっていなければ何もしません。

- GitHub Actions だけで動きます。サーバーや自宅 PC は要りません。
- 前回の状態は JSON にして、このリポジトリの [`state` ブランチ](../../tree/state)に保存します。commit の履歴が、そのままパッチノートの更新の記録になります。
- 実行時は Python の標準ライブラリだけを使います。

詳しい仕様は [SPEC.md](SPEC.md) にあります。

## 仕組み

```mermaid
flowchart LR
    cron["GitHub Actions<br>毎時 7 分"] --> fetch["一覧ページを取得<br>__NEXT_DATA__ の JSON を読む"]
    state[("state ブランチ<br>state.json")] --> compare
    fetch --> compare{"最新の記事を前回と比べる<br>記事 ID と版（rev）"}
    compare -- 変化なし --> done["何もしない"]
    compare -- 新着・更新 --> post["Discord に URL を貼る"]
    post -- 送れたときだけ --> save["state.json を commit"]
    save --> state
```

| 記事 ID | 版 | 処理 |
|---|---|---|
| 前回と違う | - | 新着として URL を貼る |
| 前回と同じ | 前回と違う | 更新として URL を貼る |
| 前回と同じ | 前回と同じ | 何もしない |

## 工夫したところ

- **HTML ではなく埋め込みの JSON を読む**: ページは Next.js 製で、記事の一覧が `<script id="__NEXT_DATA__">` に入っています。見た目の HTML を解析しないので、デザインが変わっても壊れにくいです。gzip で受け取るので、転送量は 1 回約 62KB です。
- **更新は版（`rev`）で判定する**: 文字数で比べると、パッチノートでよくある「30 → 35」のような同じ長さの書き換えを見逃します。版は記事が編集されると変わり、一覧ページを見るだけで分かります。
- **見るのは最新の 1 件だけ**: LoL の修正（ホットフィックスや「26.22b」）は今のパッチに入るので、古い記事にプレイに影響する変更は入りません。古い記事は誤字の修正などでも版が変わるため、全件を見ると不要な通知が増えます。1 回に貼るのが必ず 1 件になるので、大量に送ってしまう心配もありません。理由と、受け入れた取りこぼしは [SPEC.md の 10 章](SPEC.md#10-設計で決めたこと)にあります。
- **取りこぼさず、二重にも送らない**: Discord が受け付けた（`?wait=true`）ときだけ状態を記録します。送れなかったら次の回に送り直します。初回は記録するだけで、通知しません。
- **消えた記事に惑わされない**: 最新の記事が一覧から取り下げられても、1 つ前の記事を新着として貼りません。
- **毎回 commit しない**: 状態には「最後に確認した時刻」のような毎回変わる値を持たせていません。何かが変わった回だけ commit されます。
- **秘密情報を出さない**: Webhook の URL は GitHub の Secrets に置き、エラーメッセージやログにも出しません。`allowed_mentions` を空にして、誤ってメンションしないようにしています。
- **ネットにつながずにテストできる**: 判定の処理は送信と保存を引数で受け取るので、テストでは偽物を渡せます。

## セットアップ

1. このリポジトリを fork するか、自分のリポジトリに置く。
2. Discord のチャンネル設定 → 連携サービス → ウェブフック で Webhook を作り、URL をコピーする。
3. リポジトリの Settings → Secrets and variables → Actions → New repository secret で、`DISCORD_WEBHOOK_URL` という名前で URL を登録する。
4. Actions タブ → Watch patch notes → Run workflow で、`send_latest` にチェックを入れて実行する。最新のパッチノートの URL が Discord に届けば設定は完了。
5. もう一度、チェックを外して実行する。初回なので、最新の記事を通知せずに記録し、`state` ブランチができる。以降は毎時自動で動く。

失敗した回（一覧ページの形が変わった、Discord に送れなかったなど）は Actions の実行が失敗になり、GitHub からメールが届きます。

## 手元で動かす

```bash
python -m patchwatch --dry-run                 # 送らずに、貼る URL をログに出す（状態も保存しない）

export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python -m patchwatch --send-latest             # 最新の記事の URL を送る（状態は変えない）
python -m patchwatch --state state/state.json  # Actions と同じ処理
```

| オプション | 既定 | 内容 |
|---|---|---|
| `--state` | `state/state.json` | 状態ファイルの場所 |
| `--dry-run` | - | 送らずに貼る URL をログに出す。状態も保存しない |
| `--send-latest` | - | 最新の記事の URL を送って終わる。状態は変えない |
| `--commit-message-file` | - | `state` ブランチの commit メッセージを書き出すファイル。変化がなければ書かない |

## テスト

```bash
pip install pytest
python -m pytest
```

## 構成

```
patchwatch/
  __main__.py   コマンドの入口（引数・ログ・Actions の Summary・commit メッセージ）
  riot.py       一覧ページの取得と解析
  watcher.py    最新の記事を前回と比べて、貼るかを決める
  discord.py    Discord の Webhook に送る
  state.py      state.json の読み書き
tests/          pytest（ネットにつながずに動く）
.github/workflows/
  watch.yml     毎時の見張り
  test.yml      push と Pull Request でテスト
```

## 注意

LoL Patch Notes Watch isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

一覧ページへのアクセスは 1 時間に 1 回だけで、User-Agent でこのリポジトリを名乗っています。
