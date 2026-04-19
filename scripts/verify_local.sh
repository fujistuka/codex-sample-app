#!/usr/bin/env bash
set -euo pipefail

echo '[1/3] サーバー起動...'
python run.py > .verify_server.log 2>&1 &
PID=$!
trap 'kill "$PID" >/dev/null 2>&1 || true; rm -f .verify_server.log' EXIT

sleep 1

echo '[2/3] APIスモークテスト実行...'
python scripts/smoke_test.py

echo '[3/3] 完了 ✅ ブラウザで http://127.0.0.1:8000 を開いて確認してください。'
