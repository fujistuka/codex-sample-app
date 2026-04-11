#!/usr/bin/env bash
set -euo pipefail

echo '[1/2] Laravel sample PHP構文チェック...'
for f in $(find laravel_samples -name '*.php'); do
  php -l "$f" >/dev/null
  echo "  OK: $f"
done

echo '[2/2] 完了 ✅ 次は laravel_samples/README_VERIFY.md の手順で実Laravelへ取り込み確認してください。'
