# Laravel タスク管理アプリ向け ゲーム化機能追加（MVP設計）

> 前提: 既存に `users`, `tasks` があり、`tasks` は `user_id` を持つ。  
> 以下は **差分ベース** で追加しやすい構成です。

## 1) 追加・変更すべきテーブル設計

### `user_progresses`
ユーザーごとの進捗（XP/レベル/ストリーク/完了数）を集約。

- `id`
- `user_id` (unique)
- `total_xp` (int, default 0)
- `level` (int, default 1)
- `current_streak_days` (int, default 0)
- `longest_streak_days` (int, default 0)
- `last_completed_on` (date, nullable)
- `completed_tasks_count` (int, default 0)
- `created_at`, `updated_at`

### `achievement_badges`（マスタ）

- `id`
- `code` (unique) 例: `first_task`, `streak_7`
- `name`
- `description`
- `created_at`, `updated_at`

### `user_achievement_badges`
ユーザーの獲得実績（重複付与防止）

- `id`
- `user_id`
- `achievement_badge_id`
- `awarded_at` (timestamp)
- `created_at`, `updated_at`
- unique(`user_id`, `achievement_badge_id`)

### `task_reward_logs`
タスク完了時の計算ログ（将来分析/演出連携用）

- `id`
- `user_id`
- `task_id`
- `base_xp`
- `streak_multiplier` (decimal 4,2)
- `streak_bonus_xp`
- `final_xp`
- `streak_days_at_completion`
- `applied_streak_bonus_key` (nullable, 例: `streak_7`)
- `leveled_up` (bool)
- `level_before`
- `level_after`
- `meta` (json, nullable)
- `created_at`, `updated_at`

---

## 2) migrationコード（サンプル）

```php
// database/migrations/2026_04_11_000001_create_user_progresses_table.php
Schema::create('user_progresses', function (Blueprint $table) {
    $table->id();
    $table->foreignId('user_id')->unique()->constrained()->cascadeOnDelete();
    $table->unsignedInteger('total_xp')->default(0);
    $table->unsignedInteger('level')->default(1);
    $table->unsignedInteger('current_streak_days')->default(0);
    $table->unsignedInteger('longest_streak_days')->default(0);
    $table->date('last_completed_on')->nullable();
    $table->unsignedInteger('completed_tasks_count')->default(0);
    $table->timestamps();
});

// 2026_04_11_000002_create_achievement_badges_table.php
Schema::create('achievement_badges', function (Blueprint $table) {
    $table->id();
    $table->string('code')->unique();
    $table->string('name');
    $table->string('description');
    $table->timestamps();
});

// 2026_04_11_000003_create_user_achievement_badges_table.php
Schema::create('user_achievement_badges', function (Blueprint $table) {
    $table->id();
    $table->foreignId('user_id')->constrained()->cascadeOnDelete();
    $table->foreignId('achievement_badge_id')->constrained()->cascadeOnDelete();
    $table->timestamp('awarded_at');
    $table->timestamps();
    $table->unique(['user_id', 'achievement_badge_id']);
});

// 2026_04_11_000004_create_task_reward_logs_table.php
Schema::create('task_reward_logs', function (Blueprint $table) {
    $table->id();
    $table->foreignId('user_id')->constrained()->cascadeOnDelete();
    $table->foreignId('task_id')->constrained()->cascadeOnDelete();
    $table->unsignedInteger('base_xp');
    $table->decimal('streak_multiplier', 4, 2);
    $table->unsignedInteger('streak_bonus_xp');
    $table->unsignedInteger('final_xp');
    $table->unsignedInteger('streak_days_at_completion');
    $table->string('applied_streak_bonus_key')->nullable();
    $table->boolean('leveled_up')->default(false);
    $table->unsignedInteger('level_before');
    $table->unsignedInteger('level_after');
    $table->json('meta')->nullable();
    $table->timestamps();
});
```

初期バッジ投入Seeder:

```php
AchievementBadge::upsert([
  ['code'=>'first_task','name'=>'はじめの一歩','description'=>'初めてタスクを完了した'],
  ['code'=>'streak_7','name'=>'7日継続','description'=>'7日連続で達成した'],
  ['code'=>'streak_30','name'=>'30日継続','description'=>'30日連続で達成した'],
  ['code'=>'task_100','name'=>'100タスク達成','description'=>'タスクを100件完了した'],
  ['code'=>'level_5','name'=>'レベル5到達','description'=>'レベル5に到達した'],
], ['code'], ['name','description']);
```

---

## 3) modelコード（サンプル）

- `App\Models\UserProgress`
- `App\Models\AchievementBadge`
- `App\Models\UserAchievementBadge`
- `App\Models\TaskRewardLog`

```php
class UserProgress extends Model {
    protected $fillable = [
      'user_id','total_xp','level','current_streak_days','longest_streak_days',
      'last_completed_on','completed_tasks_count'
    ];

    protected $casts = ['last_completed_on' => 'date'];

    public function user(){ return $this->belongsTo(User::class); }
}
```

---

## 4) serviceクラス実装（MVP）

`config/gamification.php`（定数分離）

```php
return [
  'base_xp' => 10,
  'level' => [
    'xp_per_level' => 100,
  ],
  'streak_bonus' => [
    30 => 20,
    7  => 10,
    3  => 5,
  ],
  'streak_multiplier' => [
    ['min'=>30, 'max'=>null, 'multiplier'=>1.5],
    ['min'=>7,  'max'=>29,   'multiplier'=>1.2],
    ['min'=>3,  'max'=>6,    'multiplier'=>1.1],
    ['min'=>1,  'max'=>2,    'multiplier'=>1.0],
  ],
];
```

### RewardService
```php
final class RewardService {
  public function calculateXp(int $baseXp, int $streakDays): array {
    $multiplier = app(StreakService::class)->resolveMultiplier($streakDays);
    $bonus = app(StreakService::class)->resolveBonusXp($streakDays);
    $finalXp = (int) floor($baseXp * $multiplier) + $bonus;

    return [
      'base_xp' => $baseXp,
      'multiplier' => $multiplier,
      'streak_bonus_xp' => $bonus,
      'final_xp' => $finalXp,
    ];
  }
}
```

### LevelService
```php
final class LevelService {
  public function levelFromXp(int $totalXp): int {
    $per = (int) config('gamification.level.xp_per_level', 100);
    return intdiv($totalXp, $per) + 1;
  }

  public function detectLevelUp(int $beforeXp, int $afterXp): array {
    $before = $this->levelFromXp($beforeXp);
    $after = $this->levelFromXp($afterXp);
    return ['before'=>$before, 'after'=>$after, 'leveled_up'=>$after > $before];
  }
}
```

### StreakService
```php
final class StreakService {
  public function nextStreakDays(?Carbon $lastCompletedOn, Carbon $today): int {
    if (!$lastCompletedOn) return 1;
    if ($lastCompletedOn->isSameDay($today)) return 1; // 同日複数完了は維持でも可
    if ($lastCompletedOn->copy()->addDay()->isSameDay($today)) {
      return null; // 呼び出し側で current + 1
    }
    return 1;
  }

  public function resolveBonusXp(int $streakDays): int {
    foreach (config('gamification.streak_bonus') as $threshold => $bonus) {
      if ($streakDays >= (int)$threshold) return (int)$bonus;
    }
    return 0;
  }

  public function resolveMultiplier(int $streakDays): float {
    foreach (config('gamification.streak_multiplier') as $rule) {
      $min = $rule['min']; $max = $rule['max'];
      if ($streakDays >= $min && (is_null($max) || $streakDays <= $max)) {
        return (float)$rule['multiplier'];
      }
    }
    return 1.0;
  }
}
```

### AchievementService
```php
final class AchievementService {
  public function grantByProgress(User $user, UserProgress $p): array {
    $targets = [];
    if ($p->completed_tasks_count >= 1)   $targets[] = 'first_task';
    if ($p->current_streak_days >= 7)     $targets[] = 'streak_7';
    if ($p->current_streak_days >= 30)    $targets[] = 'streak_30';
    if ($p->completed_tasks_count >= 100) $targets[] = 'task_100';
    if ($p->level >= 5)                   $targets[] = 'level_5';

    $newlyAwarded = [];
    foreach ($targets as $code) {
      $badge = AchievementBadge::where('code', $code)->first();
      if (!$badge) continue;

      $exists = UserAchievementBadge::where('user_id', $user->id)
        ->where('achievement_badge_id', $badge->id)
        ->exists();
      if ($exists) continue;

      UserAchievementBadge::create([
        'user_id' => $user->id,
        'achievement_badge_id' => $badge->id,
        'awarded_at' => now(),
      ]);

      $newlyAwarded[] = $code;
    }
    return $newlyAwarded;
  }
}
```

---

## 5) タスク完了時に報酬処理を呼ぶサンプル

`TaskCompletionService` を作り、Controllerは薄くする。

```php
final class TaskCompletionService {
  public function __construct(
    private RewardService $rewardService,
    private LevelService $levelService,
    private StreakService $streakService,
    private AchievementService $achievementService,
  ) {}

  public function complete(Task $task, User $user): array {
    return DB::transaction(function () use ($task, $user) {
      if ($task->completed_at) return ['already_completed' => true];

      $task->update(['completed_at' => now(), 'status' => 'done']);

      $progress = UserProgress::firstOrCreate(['user_id' => $user->id]);

      $today = now()->startOfDay();
      $last = optional($progress->last_completed_on)?->copy();

      if (!$last) {
        $streakDays = 1;
      } elseif ($last->isSameDay($today)) {
        $streakDays = $progress->current_streak_days; // 同日維持
      } elseif ($last->copy()->addDay()->isSameDay($today)) {
        $streakDays = $progress->current_streak_days + 1;
      } else {
        $streakDays = 1;
      }

      $baseXp = (int) config('gamification.base_xp', 10);
      $xp = $this->rewardService->calculateXp($baseXp, $streakDays);

      $beforeXp = $progress->total_xp;
      $afterXp = $beforeXp + $xp['final_xp'];
      $levelInfo = $this->levelService->detectLevelUp($beforeXp, $afterXp);

      $progress->update([
        'total_xp' => $afterXp,
        'level' => $levelInfo['after'],
        'current_streak_days' => $streakDays,
        'longest_streak_days' => max($progress->longest_streak_days, $streakDays),
        'last_completed_on' => $today,
        'completed_tasks_count' => $progress->completed_tasks_count + 1,
      ]);

      TaskRewardLog::create([
        'user_id' => $user->id,
        'task_id' => $task->id,
        'base_xp' => $xp['base_xp'],
        'streak_multiplier' => $xp['multiplier'],
        'streak_bonus_xp' => $xp['streak_bonus_xp'],
        'final_xp' => $xp['final_xp'],
        'streak_days_at_completion' => $streakDays,
        'applied_streak_bonus_key' => $xp['streak_bonus_xp'] > 0 ? 'streak_bonus' : null,
        'leveled_up' => $levelInfo['leveled_up'],
        'level_before' => $levelInfo['before'],
        'level_after' => $levelInfo['after'],
      ]);

      $awarded = $this->achievementService->grantByProgress($user, $progress);

      event(new TaskRewarded($user, $task, $xp, $levelInfo, $awarded));

      return [
        'xp' => $xp,
        'level' => $levelInfo,
        'awarded_badges' => $awarded,
      ];
    });
  }
}
```

---

## 6) 実績付与サンプル処理

上記 `AchievementService::grantByProgress()` で実装。  
ポイント:
- マスタ `achievement_badges` からコードで解決
- `user_achievement_badges` unique 制約 + existsチェックで二重付与防止
- `awarded_at` を保存

---

## 7) キャラクター演出連携のイベント提案

`TaskRewarded` イベントに以下を載せる:
- `final_xp`
- `leveled_up` (bool)
- `level_before/after`
- `awarded_badges`
- `streak_days`

将来:
- Listener: `BuildCharacterCueFromReward`
- 返却用DTO例: `CharacterCue(type: 'level_up', message_key: 'level_up_5')`

演出発火タイミング:
1. タスク完了成功直後
2. レベルアップ時
3. 実績獲得時（複数なら優先順位: 実績 > レベル > 通常）

---

## 8) 簡単なテストコード（例）

```php
public function test_task_completion_adds_xp_and_levels_up(): void {
    $user = User::factory()->create();
    $task = Task::factory()->for($user)->create(['completed_at' => null]);

    UserProgress::create([
      'user_id' => $user->id,
      'total_xp' => 95,
      'level' => 1,
      'current_streak_days' => 2,
      'completed_tasks_count' => 0,
    ]);

    $result = app(TaskCompletionService::class)->complete($task, $user);

    $this->assertTrue($result['level']['leveled_up']);
    $this->assertEquals(2, $result['level']['after']);

    $progress = UserProgress::where('user_id', $user->id)->first();
    $this->assertGreaterThanOrEqual(100, $progress->total_xp);
}
```

---

## 追加/修正ファイル一覧（提案）

### 新規作成
- `config/gamification.php`
- `database/migrations/*_create_user_progresses_table.php`
- `database/migrations/*_create_achievement_badges_table.php`
- `database/migrations/*_create_user_achievement_badges_table.php`
- `database/migrations/*_create_task_reward_logs_table.php`
- `database/seeders/AchievementBadgeSeeder.php`
- `app/Models/UserProgress.php`
- `app/Models/AchievementBadge.php`
- `app/Models/UserAchievementBadge.php`
- `app/Models/TaskRewardLog.php`
- `app/Services/RewardService.php`
- `app/Services/LevelService.php`
- `app/Services/StreakService.php`
- `app/Services/AchievementService.php`
- `app/Services/TaskCompletionService.php`
- `app/Events/TaskRewarded.php`
- `tests/Feature/TaskCompletionRewardTest.php`

### 既存修正
- `app/Http/Controllers/TaskController.php`（完了処理をサービス呼び出し化）
- `app/Models/Task.php`（必要なら `completed_at` cast 追加）
- `app/Models/User.php`（progress / badges relation 追加）
