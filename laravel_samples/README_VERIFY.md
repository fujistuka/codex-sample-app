# Laravelサンプルの確認方法（これだけ見ればOK）

この `laravel_samples/` は **Laravel本体ではなくサンプル差分** です。  
そのため、このフォルダ単体では `php artisan test` は実行できません。

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
