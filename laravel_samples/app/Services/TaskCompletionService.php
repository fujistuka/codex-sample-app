<?php

namespace App\Services;

use App\Events\TaskRewarded;
use App\Models\Task;
use App\Models\TaskRewardLog;
use App\Models\User;
use App\Models\UserProgress;
use Illuminate\Support\Facades\DB;

class TaskCompletionService
{
    public function __construct(
        private RewardService $rewardService,
        private LevelService $levelService,
        private StreakService $streakService,
        private AchievementService $achievementService,
    ) {
    }

    public function complete(Task $task, User $user): array
    {
        return DB::transaction(function () use ($task, $user) {
            if ($task->completed_at) {
                return ['already_completed' => true];
            }

            $task->update(['completed_at' => now(), 'status' => 'done']);

            $progress = UserProgress::firstOrCreate(['user_id' => $user->id]);

            $today = now()->startOfDay();
            $streakDays = $this->streakService->calculateNextStreak(
                $progress->last_completed_on,
                (int) $progress->current_streak_days,
                $today,
            );

            $xp = $this->rewardService->calculate($streakDays);
            $beforeXp = (int) $progress->total_xp;
            $afterXp = $beforeXp + $xp['final_xp'];
            $level = $this->levelService->detectLevelUp($beforeXp, $afterXp);

            $progress->update([
                'total_xp' => $afterXp,
                'level' => $level['after'],
                'current_streak_days' => $streakDays,
                'longest_streak_days' => max((int) $progress->longest_streak_days, $streakDays),
                'last_completed_on' => $today,
                'completed_tasks_count' => (int) $progress->completed_tasks_count + 1,
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
                'leveled_up' => $level['leveled_up'],
                'level_before' => $level['before'],
                'level_after' => $level['after'],
            ]);

            $awardedBadges = $this->achievementService->grantByProgress($user, $progress->fresh());

            event(new TaskRewarded($user, $task, $xp, $level, $awardedBadges, $streakDays));

            return [
                'xp' => $xp,
                'level' => $level,
                'awarded_badges' => $awardedBadges,
                'streak_days' => $streakDays,
            ];
        });
    }
}
