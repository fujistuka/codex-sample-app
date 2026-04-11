$ErrorActionPreference = 'Stop'

if (-not (Get-Command php -ErrorAction SilentlyContinue)) {
    Write-Error 'php command was not found. Install PHP and add it to PATH.'
    exit 1
}

Write-Host 'Starting PHP demo server on http://127.0.0.1:8081'
Write-Host 'Open the URL in your browser to preview gamification logic.'
php -S 127.0.0.1:8081 -t laravel_samples/demo
