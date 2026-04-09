# codex-sample-app

シンプルなToDoアプリです。

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
