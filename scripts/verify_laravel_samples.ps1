Write-Host "[0/2] PHPコマンド確認..."
if (-not (Get-Command php -ErrorAction SilentlyContinue)) {
    Write-Error "php コマンドが見つかりません。PHPをインストールし、PATHへ追加してください。例: scoop install php"
    exit 1
}

Write-Host "[1/2] Laravel sample PHP構文チェック..."
$files = Get-ChildItem -Path laravel_samples -Recurse -Filter *.php
foreach ($f in $files) {
    php -l $f.FullName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PHP lint failed: $($f.FullName)"
    }
    Write-Host "  OK: $($f.FullName)"
}

Write-Host "[2/2] 完了 ✅ 次は laravel_samples/README_VERIFY.md の手順で実Laravelへ取り込み確認してください。"
