# LoL Patch Notes Watch 仕様書

最終更新: 2026-11-11

## 1. 目的

League of Legends の日本語パッチノート一覧を定期的に確認し、新しい記事や更新された記事があれば、その URL を Discord に貼る。何も変わっていなければ何もしない。

企業に見せるポートフォリオとしても使う。そのため、動いている様子（実行ログ・状態の履歴）を GitHub 上で誰でも見られる形にする。

対象（決定）:

| 項目 | 値 |
|---|---|
| ゲーム | League of Legends のみ |
| 言語 | 日本語（`ja-jp`）のみ |
| 見るページ | パッチノート一覧ページだけ（記事ページは開かない） |
| 通知する変化 | 新しい記事と、更新された記事 |
| 通知の中身 | 記事の URL だけ |
| 通知先 | Discord の Webhook（1 チャンネル） |

## 2. 全体構成

```
[GitHub Actions] 1 時間ごと
  1. state ブランチから前回の状態（state.json）を取り出す
  2. パッチノート一覧ページを取得し、記事ごとの ID・版（rev）・URL を取り出す
  3. 前回と比べる
  4. 新しい記事・版が変わった記事があれば、その URL を Discord に貼る
  5. 状態に変化があれば state.json を state ブランチに commit して push
```

- 実行は GitHub Actions で行う。自宅 PC は使わない。
- 状態は JSON ファイル 1 つ（`state.json`）。コードと同じリポジトリの、専用の `state` ブランチに置く。
- OTP Off-Role Insights とは別のリポジトリにする。
- 実行時に外部ライブラリは使わない（Python 標準ライブラリのみ）。テストだけ pytest を使う。

## 3. 一覧ページ

`https://www.leagueoflegends.com/ja-jp/news/tags/patch-notes/`

ページは Next.js で作られていて、表示に使うデータが `<script id="__NEXT_DATA__">` に JSON で入っている。見た目の HTML ではなくこの JSON を読むので、デザインの変更では壊れにくい。

記事の一覧は `props.pageProps.page.blades` のうち `type` が `articleCardGrid` のものの `items`（2026-11-11 時点で 177 件、新しい順）。1 件ごとに次の値を使う。

| 値 | 場所 | 例 | 使い道 |
|---|---|---|---|
| 記事 ID | `analytics.contentId` | `patchNote.f9b9c125-…ja-jp` | 記事を見分ける |
| 版 | `analytics.rev` | `MoUhEtOWHNIDVAplxLwMyl` | 記事が更新されたかを見分ける。記事が編集されると変わる |
| URL | `action.payload.url` | `/ja-jp/news/game-updates/league-of-legends-patch-26-22-notes` | Discord に貼る |
| タイトル | `title` | リーグ・オブ・レジェンド パッチノート 26.22 | ログと commit メッセージ |
| 公開日時 | `publishedAt` | `2026-11-03T19:00:00.000Z` | 状態ファイルの並び順 |

URL は相対パスなので `https://www.leagueoflegends.com` を付ける。

アクセスのマナー:
- 一覧ページを 1 時間に 1 回取得するだけ。
- User-Agent で名乗る: `lol-patch-notes-watch/<版> (+https://github.com/a-a81/lol-patch-notes-watch)`。
- 5xx・429・通信エラーは 5 秒、10 秒と待って最大 3 回まで試す。それ以外の 4xx はすぐ諦める。

## 4. 変化の判定

一覧の記事を古い順に 1 件ずつ見る（Discord に時系列で並ぶように）。

| 前回の状態 | 一覧の版 | 処理 |
|---|---|---|
| ない | - | 新しい記事。URL を貼る |
| ある | 違う | 更新された記事。URL を貼る |
| ある | 同じ | 何もしない |

- 版（`rev`）は、本文以外の変更（画像やメタ情報）でも変わることがある。その場合も更新として URL を貼る。中身を見て区別することはしない（一覧ページだけを見るため）。
- 一覧から消えた記事は、状態に残したまま何もしない。

### 4.1 初回

状態ファイルがない（または記事が 1 件もない）ときは初回として扱う。一覧の全記事を、通知せずに記録する。次の回から通知が始まる。

### 4.2 想定外のときの扱い

| 状況 | 扱い | 理由 |
|---|---|---|
| 一覧ページに `__NEXT_DATA__` や記事の一覧がない | 失敗として終わる。状態は変えない | サイトの作りが変わった可能性が高い。気づけるように失敗にする（7.3） |
| 1 回で変化した記事が 6 件以上（`--max-changes`、既定 5） | URL を貼らずに全部記録し、失敗として終わる | 記事 ID の形が変わると、全記事が「新しい記事」に見えて大量に貼ってしまう。実際、ID には `patchNote.` で始まるものと始まらないものが混ざっている |
| Discord への送信に失敗 | その記事と、それより新しい記事は送らず、状態も更新しない。次回もう一度送る。失敗として終わる | 送信に成功したものだけ記録するので、取りこぼさない。後ろの記事も止めるので、Discord での並びが入れ替わらない |

## 5. Discord 通知

1 記事につき 1 メッセージで、記事の URL だけを送る。Discord がリンクのプレビュー（タイトル・画像・紹介文）を自動で付ける。

```
https://www.leagueoflegends.com/ja-jp/news/game-updates/league-of-legends-patch-26-22-notes
```

送信:
- Webhook の URL に `?wait=true` を付け、Discord が受け付けたことを確かめる。
- 429 は Discord が返す `retry_after` 秒だけ待ってやり直す。5xx と通信エラーも待ってやり直す。最大 3 回。
- `allowed_mentions` を空にして、誤ってメンションしないようにする。
- エラーのメッセージやログに Webhook の URL を出さない（URL を知っていれば誰でも投稿できるため）。

確認用の送信: `--send-latest` を付けて動かすと、一覧の最新の記事の URL を 1 件送る。状態は変えない。Webhook の設定を確かめるのに使う。GitHub Actions では手動実行の画面からチェックを入れて使う。

## 6. 状態ファイル `state.json`

`state` ブランチの直下に置く。人が読めるよう字下げ 2 で書き、記事は公開日時の新しい順に並べる。保存は一時ファイルに書いてから置き換える（途中で落ちても前回のファイルが残る）。

```json
{
  "schemaVersion": 1,
  "articles": {
    "patchNote.f9b9c125-2f9c-4d0c-b9cf-02b90d051ac6.ja-jp": {
      "title": "リーグ・オブ・レジェンド パッチノート 26.22",
      "url": "https://www.leagueoflegends.com/ja-jp/news/game-updates/league-of-legends-patch-26-22-notes",
      "publishedAt": "2026-11-03T19:00:00.000Z",
      "rev": "MoUhEtOWHNIDVAplxLwMyl"
    }
  }
}
```

状態は、何かが変わった回だけ commit する。「最後に確認した時刻」のような毎回変わる値は持たない（毎時 commit されてしまうため）。確認した時刻は Actions の実行履歴で分かる。

`state` ブランチの commit の履歴が、そのままパッチノートの更新の記録になる。commit メッセージは変化の内容にする。

| 変化 | commit メッセージの例 |
|---|---|
| 初回 | `Baseline 177 articles` |
| 新しい記事 | `New: リーグ・オブ・レジェンド パッチノート 26.23` |
| 更新された記事 | `Updated: リーグ・オブ・レジェンド パッチノート 26.22` |

## 7. 実行環境（GitHub Actions）

### 7.1 見張りのワークフロー `.github/workflows/watch.yml`

| 項目 | 値 |
|---|---|
| きっかけ | 毎時 7 分（cron `7 * * * *`、UTC）と手動実行 |
| 手動実行の入力 | `send_latest`（5 章の確認用の送信。既定はオフ） |
| 権限 | `contents: write`（`state` ブランチへの push のため） |
| 同時実行 | `concurrency` で 1 つだけ。前の回が動いていたら終わるのを待つ |
| 時間の上限 | 5 分 |
| Python | 3.12 |

00 分ちょうどは GitHub 全体で混み、実行が遅れやすいので 7 分にする。cron の実行は数分〜数十分遅れることがある。

手順:
1. `main` をチェックアウトする。
2. `state` ブランチを `state/` に取り出す（`git worktree`）。まだなければ、空の `state` ブランチを作る。
3. `python -m patchwatch --state state/state.json` を実行する。
4. 3 が失敗しても（キャンセル以外）、`state/state.json` に変化があれば commit して `state` ブランチに push する。送信に成功した分の記録を残すため。

`state` ブランチは見張りのワークフローしか書き込まないので、`main` の開発と衝突しない。強制 push はしない。

テストのワークフロー `.github/workflows/test.yml`: `main` への push と Pull Request で pytest を動かす。

### 7.2 用意するもの

| もの | 場所 |
|---|---|
| Discord の Webhook URL | リポジトリの Settings → Secrets and variables → Actions に `DISCORD_WEBHOOK_URL` として登録する。コードや会話には書かない |
| Actions の書き込み権限 | ワークフローに `permissions: contents: write` を書く。リポジトリの設定で Actions の書き込みが禁止されていないこと |

### 7.3 失敗に気づく方法

- プログラムは、4.2 の失敗が 1 つでもあれば終了コード 1 で終わる。Actions の実行が失敗になる。
- GitHub は、定期実行が失敗するとワークフローを最後に編集した人にメールを送る（既定の設定）。
- 実行ごとの結果（貼った URL・失敗）を Actions の実行画面の Summary に出す。

### 7.4 料金と制限

- 公開リポジトリなら Actions は無料。非公開でも、1 回 1 分未満 × 月 720 回で、無料枠（月 2,000 分）に収まる。
- 公開リポジトリで 60 日間活動がないと、定期実行が自動で止まることがある。止まったら Actions の画面から有効に戻す。

## 8. プログラム構成

```
patchwatch/
  __init__.py   版
  __main__.py   コマンドの入口。引数・環境変数・ログ・Summary・commit メッセージ
  riot.py       一覧ページの取得と、記事の値の取り出し（3 章）
  watcher.py    前回と比べて、貼る記事と記録する記事を決める（4 章）
  discord.py    Discord に URL を送る（5 章）
  state.py      state.json の読み書き（6 章）
tests/
.github/workflows/watch.yml
.github/workflows/test.yml
SPEC.md
README.md
pyproject.toml
```

`watcher.py` は、通知の送信を引数で受け取る。テストでは偽物を渡し、ネットにつながずに判定を確かめる。

コマンド: `python -m patchwatch [オプション]`

| オプション | 既定 | 内容 |
|---|---|---|
| `--state` | `state/state.json` | 状態ファイルの場所 |
| `--max-changes` | 5 | 1 回に貼る URL の上限（4.2） |
| `--dry-run` | - | 送らずに、貼る URL をログに出す。状態も保存しない |
| `--send-latest` | - | 最新の記事の URL を 1 件送って終わる（5 章） |
| `--commit-message-file` | - | commit メッセージ（6 章）を書き出すファイル。ワークフローが使う |

環境変数 `DISCORD_WEBHOOK_URL` に Webhook の URL を入れる。`--dry-run` 以外で未設定なら、終了コード 2 で終わる。

## 9. テスト

pytest で、ネットにつながずに動かす。テスト用のページは、実際の一覧ページと同じ形（`__NEXT_DATA__`）を小さく再現したものを使う。

| 対象 | 確かめること |
|---|---|
| 一覧の解析 | 値を取り出せる。URL が絶対パスになる。`__NEXT_DATA__` や一覧がなければ `ScrapeError` |
| 判定 | 初回は貼らない。新しい記事を貼る。版が変わった記事を貼る。変化がなければ何もしない。古い順に貼る。送信に失敗したら記録せず、次回送り直す。変化が多すぎたら貼らない |
| Discord | 送る中身が URL だけ。429 で待ってやり直す。エラーに Webhook の URL を出さない |
| 状態ファイル | 読み書きで中身が変わらない。ファイルがなければ空の状態。`schemaVersion` が違えばエラー |

## 10. 設計で決めたこと

| 項目 | 決定 | 比べたもの | 理由 |
|---|---|---|---|
| 実行場所 | GitHub Actions | 自宅 PC の夜間処理に組み込む / 自宅 PC で別タスク | PC がスリープ中でも動く。実行ログを誰でも見られ、fork すれば同じものを動かせる |
| 状態の保存先 | JSON を `state` ブランチに commit | SQLite / Actions のキャッシュ | Actions は毎回まっさらな環境なので、状態をリポジトリに残す。JSON なら GitHub 上で中身と差分が読め、履歴が更新の記録になる。SQLite はバイナリで差分が読めない。キャッシュは 7 日使わないと消え、中身も見られない |
| 更新の判定 | 一覧の版（`rev`）を比べる | 記事ページを開いて文字数や本文を比べる | 一覧 1 回で全記事の変化が分かる。文字数では「30 → 35」のような同じ長さの書き換えを見逃す |
| 通知の中身 | URL だけ | タイトルや変更点をまとめた埋め込み | 中身は記事を開けば分かる。Discord のリンクのプレビューで十分 |
| リポジトリ | OTP Off-Role Insights とは別 | 同じリポジトリに入れる | 機能として独立していて、見る人に伝わりやすい |

## 11. 未決定事項

| # | 項目 | 案 | 決め方 |
|---|---|---|---|
| 1 | リポジトリ名 | `lol-patch-notes-watch` | 作る前に決める。User-Agent の URL も合わせる |
| 2 | 公開か非公開か | 公開（ポートフォリオとして見せるため） | 作る前に決める |
| 3 | 確認の間隔 | 1 時間ごと | 運用して、通知の遅れが気になれば 30 分ごとにする |
| 4 | 新しい記事と更新を区別して見せるか | 区別しない（URL だけ） | 運用して分かりにくければ、URL の前に「新着」「更新」を付ける |
| 5 | README の言語 | 日本語 | 応募先に合わせる。英語を足すなら `README.en.md` |
