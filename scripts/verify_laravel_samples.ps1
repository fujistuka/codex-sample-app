$ErrorActionPreference = 'Stop'

Write-Host '[0/3] Checking php command...'
if (-not (Get-Command php -ErrorAction SilentlyContinue)) {
    Write-Error 'php command was not found. Install PHP and add it to PATH (example: scoop install php).'
    exit 1
}

Write-Host '[1/3] Validating current folder...'
if (-not (Test-Path -Path 'laravel_samples' -PathType Container)) {
    Write-Error 'laravel_samples folder not found. Run this script from the repository root.'
    exit 1
}

if (Test-Path -Path 'artisan' -PathType Leaf) {
    Write-Host 'Note: artisan was found in this folder.'
} else {
    Write-Host 'Note: no artisan file here. This repository contains Laravel sample files only.'
    Write-Host '      Use laravel_samples/README_VERIFY.md for integration steps into a real Laravel app.'
}

Write-Host '[2/3] Running PHP lint for laravel_samples...'
$files = Get-ChildItem -Path 'laravel_samples' -Recurse -Filter '*.php'
foreach ($f in $files) {
    php -l $f.FullName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PHP lint failed: $($f.FullName)"
    }
    Write-Host "  OK: $($f.FullName)"
}

Write-Host '[3/3] Done.'
