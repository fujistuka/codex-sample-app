<?php
$baseXp = 10;
$multiplierRules = [
    ['min' => 30, 'value' => 1.5],
    ['min' => 7, 'value' => 1.2],
    ['min' => 3, 'value' => 1.1],
    ['min' => 1, 'value' => 1.0],
];
$bonusRules = [
    ['min' => 30, 'value' => 20],
    ['min' => 7, 'value' => 10],
    ['min' => 3, 'value' => 5],
];

function levelFromXp(int $totalXp): int
{
    return intdiv($totalXp, 100) + 1;
}

function multiplierFromStreak(int $streak, array $rules): float
{
    foreach ($rules as $rule) {
        if ($streak >= $rule['min']) {
            return (float)$rule['value'];
        }
    }

    return 1.0;
}

function bonusFromStreak(int $streak, array $rules): int
{
    foreach ($rules as $rule) {
        if ($streak >= $rule['min']) {
            return (int)$rule['value'];
        }
    }

    return 0;
}

function earnedBadges(int $completedTasks, int $streak, int $nextLevel): array
{
    $badges = [];

    if ($completedTasks >= 1) {
        $badges[] = 'first_task';
    }
    if ($streak >= 7) {
        $badges[] = 'streak_7';
    }
    if ($streak >= 30) {
        $badges[] = 'streak_30';
    }
    if ($completedTasks >= 100) {
        $badges[] = 'task_100';
    }
    if ($nextLevel >= 5) {
        $badges[] = 'level_5';
    }

    return $badges;
}

$currentXp = max(0, (int)($_POST['current_xp'] ?? 95));
$completedTasks = max(0, (int)($_POST['completed_tasks'] ?? 0));
$streakDays = max(1, (int)($_POST['streak_days'] ?? 1));

$multiplier = multiplierFromStreak($streakDays, $multiplierRules);
$bonus = bonusFromStreak($streakDays, $bonusRules);
$gainedXp = (int)floor($baseXp * $multiplier) + $bonus;
$nextXp = $currentXp + $gainedXp;
$prevLevel = levelFromXp($currentXp);
$nextLevel = levelFromXp($nextXp);
$leveledUp = $nextLevel > $prevLevel;
$badges = earnedBadges($completedTasks + 1, $streakDays, $nextLevel);
?>
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Laravel Gamification Preview</title>
  <style>
    body { font-family: sans-serif; margin: 24px; background: #f7f7f7; color: #222; }
    .card { background: #fff; border: 1px solid #ddd; border-radius: 12px; padding: 16px; max-width: 760px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    label { font-size: 14px; display: block; margin-bottom: 6px; }
    input { width: 100%; padding: 8px; }
    button { margin-top: 12px; padding: 10px 14px; }
    .result { margin-top: 16px; background: #f9fbff; border: 1px solid #cfe3ff; border-radius: 8px; padding: 12px; }
  </style>
</head>
<body>
  <h1>PHP画面での報酬機能プレビュー</h1>
  <p>この画面は Laravel 本体なしで、追加したゲーム化ロジックを目視確認するための簡易デモです。</p>

  <div class="card">
    <form method="post">
      <div class="grid">
        <div>
          <label for="current_xp">現在XP</label>
          <input id="current_xp" name="current_xp" type="number" value="<?= htmlspecialchars((string)$currentXp, ENT_QUOTES, 'UTF-8') ?>">
        </div>
        <div>
          <label for="completed_tasks">現在の完了タスク数</label>
          <input id="completed_tasks" name="completed_tasks" type="number" value="<?= htmlspecialchars((string)$completedTasks, ENT_QUOTES, 'UTF-8') ?>">
        </div>
        <div>
          <label for="streak_days">連続日数</label>
          <input id="streak_days" name="streak_days" type="number" value="<?= htmlspecialchars((string)$streakDays, ENT_QUOTES, 'UTF-8') ?>">
        </div>
      </div>
      <button type="submit">タスク完了をシミュレート</button>
    </form>

    <div class="result">
      <p><strong>計算式:</strong> floor(<?= $baseXp ?> × <?= number_format($multiplier, 1) ?>) + <?= $bonus ?> = <strong><?= $gainedXp ?> XP</strong></p>
      <p><strong>XP:</strong> <?= $currentXp ?> → <?= $nextXp ?></p>
      <p><strong>レベル:</strong> Lv<?= $prevLevel ?> → Lv<?= $nextLevel ?> <?= $leveledUp ? '(Level Up!)' : '' ?></p>
      <p><strong>今回の実績候補:</strong> <?= $badges ? htmlspecialchars(implode(', ', $badges), ENT_QUOTES, 'UTF-8') : 'なし' ?></p>
    </div>
  </div>
</body>
</html>
