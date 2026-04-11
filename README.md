# codex-sample-app

シンプルなToDoアプリ（MVP）です。以下を実装しています。

- 簡易ログイン（ID/パスワード、セッション30日保持）
- ToDoの追加・一覧
- 完了/未完了切り替え
- 編集・削除
- 期限日・優先度・タグ
- 検索・フィルタ・ソート・ページング
- SQLite保存（接続が切れても再接続後に保持）
- タイトル下にカレンダー表示
- 応援キャラクター + 吹き出しランダムメッセージ
- キャラクター画像のフォルダ/ファイル指定

## ログイン情報（初期）

- ID: `admin`
- パスワード: `password`

## 起動方法

### 共通（まずはこれでOK）

```bash
python run.py
```

ブラウザで `http://127.0.0.1:8000` を開いてください。

### 依存関係をインストールできる場合（FastAPI/uvicornを明示利用）

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Windowsでの注意

以前の検証コマンドは **bash向け**（`/tmp`, `$TOKEN`, `&&`, `;` など）でした。  
`cmd.exe` ではそのまま動きません。

Windowsでは次のどちらかを使ってください。

1. **アプリだけ起動してブラウザ確認（推奨）**
   - `python run.py`
2. **APIの動作確認**
   - 別ターミナルで `python scripts/smoke_test.py`

## クロスプラットフォームAPIスモークテスト

サーバー起動後に実行:

```bash
python scripts/smoke_test.py
```

このスクリプトは以下を自動確認します。

- login
- list
- create
- filter/sort/pagination
- toggle
- update
- delete

## キャラクター画像の設定

右側の「応援キャラクター」カードで以下を指定できます。

- 画像フォルダ（URLパス）
- 画像ファイル名

例: `/static/character` と `default-girl.svg`

任意画像を使う場合は、`static/character/` に画像ファイル（png/jpg/webp/svg）を置いて指定してください。

## API（最小）

- `POST /api/login`
- `GET /api/me`
- `GET /api/todos`
- `POST /api/todos`
- `PUT /api/todos/{id}`
- `PATCH /api/todos/{id}/toggle`
- `DELETE /api/todos/{id}`
