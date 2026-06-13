# 商品・部門分析アプリ

もみじ屋専用の軽量Streamlitアプリです。既存の売上分析アプリには統合せず、Google Sheets上の「商品別売上」「部門別売上」だけを読み込んで、商品・部門分析を行います。

## 使用するスプレッドシート

https://docs.google.com/spreadsheets/d/1bBsJxUtDSTk7Qkfn_Q2tKKVo-0AL_aFCkivalZTtGWc/edit?gid=1368968312#gid=1368968312

必要なシート名は以下の2つです。

- 商品別売上
- 部門別売上

このアプリは分析用シート、RawDataシート、設定シート、ログシートを作成しません。

## 現在の実装範囲

MVP第1段階から第3段階までの基本機能を実装しています。

- Google Sheetsから2シートを読み込み
- 店舗選択
- 月選択
- 月次サマリー
- 部門別構成比
- 商品別TOP
- ABC分析
- 前月比ランキング
- 前年同月比ランキング
- 任意月比較ランキング
- 新規/復活商品の表示
- 商品別の店舗間比較
- 部門別の店舗間比較
- 店舗間ギャップの大きい商品TOP
- おすすめ強化候補
- 整理確認候補
- POP候補
- キャッシュクリア
- 商品分析からデリバリー売上を除外する設定

重い全商品一覧は初期表示せず、必要な分析だけを選択して表示します。

## Streamlit secretsの設定

`.streamlit/secrets.toml.example` を参考に、ローカルでは `.streamlit/secrets.toml` を作成してください。

```toml
[google_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-cert-url"

[app]
spreadsheet_id = "1bBsJxUtDSTk7Qkfn_Q2tKKVo-0AL_aFCkivalZTtGWc"

[auth]
app_password = "change-this-password"
```

サービスアカウントのメールアドレスを対象スプレッドシートに閲覧者として共有してください。

既存の売上分析アプリで使っているsecretsが `[gcp_service_account]` という名前の場合も、このアプリは読み込めます。新規に設定する場合は `[google_service_account]` を推奨します。

`[auth]` の `app_password` は、アプリを開く人にだけ共有するログイン用パスワードです。Googleの秘密鍵とは別のものです。Streamlit Cloudに公開する場合も、Cloud側のSecretsに同じ `[auth]` を設定してください。

## ローカル実行方法

```powershell
cd "C:\Users\momij\OneDrive\ドキュメント\New project\momijiya-menu-analysis-app"
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\streamlit run app.py
```

このPCで `python` がPATHに無い場合は、以下のようにフルパスで実行できます。

```powershell
cd "C:\Users\momij\OneDrive\ドキュメント\New project\momijiya-menu-analysis-app"
& "C:\Users\momij\AppData\Local\Programs\Python\Python314\python.exe" -m pip install --user -r requirements.txt
& "C:\Users\momij\AppData\Local\Programs\Python\Python314\python.exe" -m streamlit run app.py
```

日本語を含むOneDriveパス配下で `.venv` がうまく起動しない場合は、上記の `--user` インストールを使うか、日本語を含まない短いパスにプロジェクトを置いて仮想環境を作成してください。

## Streamlit Cloudへのデプロイ

1. この `momijiya-menu-analysis-app` をGitHubリポジトリに配置します。
2. Streamlit Cloudで新規アプリを作成し、`app.py` をエントリーポイントにします。
3. Streamlit CloudのSecretsに `.streamlit/secrets.toml.example` と同じ内容を登録します。
4. サービスアカウントがスプレッドシートを閲覧できることを確認します。
5. デプロイ後、サイドバーで店舗と月を選び、月次サマリー、部門分析、商品TOP分析を確認します。

## キャッシュ方針とクリア方法

Google Sheets読み込み、集計結果は `st.cache_data(ttl=21600)` で6時間キャッシュしています。店舗一覧・月一覧は24時間キャッシュです。月1回更新のデータなので、必要に応じてTTLは `utils/sheets.py` と `utils/transform.py` の `CACHE_TTL_SECONDS` を変更してください。

画面左の「キャッシュクリア」ボタンを押すと、データキャッシュと接続キャッシュをクリアします。

## 最初の動作確認手順

1. secretsを設定します。
2. `streamlit run app.py` で起動します。
3. 店舗を「神田店」にします。
4. 月を「2026-04」にします。
5. 部門分析タブで部門別構成比が表示されることを確認します。
6. 商品TOP分析タブで商品別TOP20が表示されることを確認します。
7. 画面を再読み込みし、毎回Google Sheets読み込みが走らずキャッシュが効いていることを確認します。
8. 初期表示で全商品一覧が展開表示されていないことを確認します。

## 数値がスマレジ管理画面とズレる場合の確認ポイント

- 返品、取消、値引、セット、バンドルの扱い
- 部門売り、コース内訳、商品親子行の扱い
- 税区分、内税、外税、税抜/税込の基準
- 締め日、営業日、取引日の基準
- 商品名、商品コード、部門名の変更
- スマレジAPI集計時点と管理画面表示時点の差

商品別売上の合計と部門別売上の合計は完全一致しない可能性があります。その場合、このアプリでは月次総額の基準を部門別売上にしています。

商品TOP分析とABC分析では、初期設定でデリバリー売上を除外します。月次サマリーと部門分析では売上全体を確認するため、デリバリーも含めて表示します。

## 注意

商品名変更や商品コード変更があると、同じ商品でも別商品として扱われる可能性があります。部門名変更があると、部門比較にズレが出る可能性があります。原価が空欄または0の場合、粗利分析は参考値にしてください。

## 今後の改善案

- 店舗別の活用メモを部門・商品ごとに強化
- 改善候補の条件を店長会議で確認しながら調整
- 季節商品、限定商品、コース内訳を除外/注意表示する設定
- 粗利・原価データが安定した場合の粗利分析追加
- 既存売上分析アプリ側へのリンク追加
