# Streamlit Cloud公開手順

このアプリを別の場所・別PCから使うには、Streamlit Cloudにデプロイします。

## こちらで準備済みのこと

- `app.py` をStreamlit Cloudで実行できる構成にしています。
- `requirements.txt` に必要ライブラリを入れています。
- `.streamlit/secrets.toml` はGitHubに上げない設定にしています。
- `.streamlit/secrets.toml.example` にCloudへ貼り付ける形式のサンプルを用意しています。
- アプリ起動時にパスワードログインを出すようにしています。

## 人間が必要な作業

以下はブラウザでのログインや秘密情報の貼り付けが必要なため、人間が行う必要があります。

1. GitHubにこのアプリ用リポジトリを作る
2. このフォルダのコードをGitHubへpushする
3. Streamlit Cloudにログインする
4. GitHubリポジトリを選んでアプリを作成する
5. Streamlit CloudのSecretsに `.streamlit/secrets.toml` の内容を貼り付ける
6. デプロイ後のURLを社内メンバーへ共有する
7. ログイン用パスワードを許可した人にだけ共有する

## GitHubへ上げてよいファイル

- `app.py`
- `requirements.txt`
- `README.md`
- `STREAMLIT_CLOUD_DEPLOY.md`
- `.gitignore`
- `.streamlit/secrets.toml.example`
- `utils/` 配下のPythonファイル

## GitHubへ上げてはいけないファイル

- `.streamlit/secrets.toml`
- `.streamlit/secrets.toml.txt`
- GoogleサービスアカウントのJSONファイル
- `streamlit.out.log`
- `streamlit.err.log`
- `.venv/`
- `__pycache__/`

## Streamlit Cloudでの設定

Streamlit Cloudでアプリ作成時、以下を指定します。

- Repository: GitHubに作成したこのアプリのリポジトリ
- Branch: `main`
- Main file path: `app.py`

Secretsには、ローカルの以下のファイル内容を貼り付けます。

```text
C:\Users\momij\OneDrive\ドキュメント\New project\momijiya-menu-analysis-app\.streamlit\secrets.toml
```

貼り付ける内容には以下が含まれます。

- `[gcp_service_account]` または `[google_service_account]`
- `[app]`
- `[auth]`

## 公開後の確認

1. Streamlit Cloudの公開URLを開く
2. ログイン画面が出ることを確認
3. ログイン用パスワードで入る
4. 店舗を `神田店` にする
5. 月を `2026-04` にする
6. 部門分析、商品TOP分析、前月比・前年比ランキング、店舗間比較、改善候補を見る

## 注意

このアプリのパスワードログインは、社内共有向けの簡易認証です。公開URLを知っていてもパスワードがなければ中には入れませんが、パスワードを共有しすぎると誰でも入れる状態になります。退職者や不要な共有が出た場合は、Streamlit CloudのSecretsで `[auth] app_password` を変更してください。
