# Laravelサンプルの確認方法（これだけ見ればOK）

この `laravel_samples/` は **Laravel本体ではなくサンプル差分** です。  
そのため、このフォルダ単体では `php artisan test` は実行できません。


## 0) まず `php` コマンドが使えるか確認（Windows）

## Important

- This repository is **not** a Laravel application root. It does not contain an `artisan` file.
- So, `php artisan ...` will fail in this repository with: `Could not open input file: artisan`.
- Run `php artisan ...` only inside your real Laravel project root (where `artisan` exists).


PowerShellで以下を実行:

```powershell
php -v
```

`php : 用語 'php' は...` のようなエラーが出る場合は、PHPが未インストールまたはPATH未設定です。

### 例: scoop で入れる場合

```powershell
scoop install php
php -v
```

### 例: chocolatey で入れる場合

```powershell
choco install php
php -v
```

> XAMPP/Laragon利用時も、`php.exe` のあるフォルダを PATH に通してください。

---
## 1) このリポジトリ内でできる確認

### A. PHP構文チェック（必須）

```bash
./scripts/verify_laravel_samples.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_laravel_samples.ps1
```

これで `laravel_samples/**/*.php` の構文エラー有無を確認できます。

---


## 1.5) PHP画面で確認する（このリポジトリだけでOK）

`python run.py` は Python アプリ用なので、Laravelサンプルの確認には使いません。  
PHP側の画面確認は次を使ってください。

### Mac / Linux / Git Bash

```bash
./scripts/run_php_demo.sh
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_php_demo.ps1
```

起動後にブラウザで `http://127.0.0.1:8081` を開くと、
XP倍率・ストリークボーナス・レベルアップ・実績候補を画面で確認できます。

---

## 2) 実Laravelプロジェクトに取り込んだ後の確認

1. `config/gamification.php` を `config/` へコピー
2. migrations / models / services / events / seeder / test を対応ディレクトリへコピー
3. 以下を実行

```bash
php artisan migrate
php artisan db:seed --class=AchievementBadgeSeeder
php artisan test --filter=TaskCompletionRewardTest
```

### 最低限の動作確認シナリオ

- タスク完了前: `total_xp=95, level=1`
- タスク完了実行
- 完了後:
  - `total_xp >= 100`
  - `level = 2`
  - `task_reward_logs` に1件追加
  - 条件を満たす実績が `user_achievement_badges` に追加

---

## 3) 期待する確認ポイント

- `RewardService`: `final_xp = floor(base_xp * multiplier) + streak_bonus` になっている
- `LevelService`: 100XP単位でレベルが上がる
- `StreakService`: 連続日数と倍率/ボーナスが設定値どおり
- `AchievementService`: 同一バッジの二重付与が起きない
- `TaskCompletionService`: トランザクション内で完了→報酬→実績→イベント発火の順で処理される
