Write-Host "[1/3] サーバー起動..."
$proc = Start-Process -FilePath python -ArgumentList "run.py" -PassThru -WindowStyle Hidden

try {
    Start-Sleep -Seconds 1
    Write-Host "[2/3] APIスモークテスト実行..."
    python scripts/smoke_test.py
    if ($LASTEXITCODE -ne 0) {
        throw "smoke_test failed"
    }

    Write-Host "[3/3] 完了 ✅ ブラウザで http://127.0.0.1:8000 を開いて確認してください。"
}
finally {
    if ($proc -and !$proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
}
