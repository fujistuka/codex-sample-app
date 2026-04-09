# codex-sample-app

シンプルなToDoアプリ（MVP）です。以下を実装しています。

- 簡易ログイン（ID/パスワード）
- ToDoの追加・一覧
- 完了/未完了切り替え
- 編集・削除
- 期限日・優先度・タグ
- 検索・フィルタ・ソート・ページング
- SQLite保存

## ログイン情報（初期）

- ID: `admin`
- パスワード: `password`

## 起動方法

### 依存関係をインストールできる場合（推奨）

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 依存関係をインストールできない場合（フォールバック）

```bash
python run.py
```

`http://127.0.0.1:8000` をブラウザで開くと利用できます。

## API（最小）

- `POST /api/login`
- `GET /api/me`
- `GET /api/todos`
- `POST /api/todos`
- `PUT /api/todos/{id}`
- `PATCH /api/todos/{id}/toggle`
- `DELETE /api/todos/{id}`
