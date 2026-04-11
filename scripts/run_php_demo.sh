#!/usr/bin/env bash
set -euo pipefail

if ! command -v php >/dev/null 2>&1; then
  echo "php command not found. Install PHP first."
  exit 1
fi

echo "Starting PHP demo server on http://127.0.0.1:8081"
echo "Open the URL in your browser to preview gamification logic."
php -S 127.0.0.1:8081 -t laravel_samples/demo
