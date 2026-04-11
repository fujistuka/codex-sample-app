<?php

namespace App\Services;

use App\Models\AchievementBadge;
use App\Models\User;
use App\Models\UserAchievementBadge;
use App\Models\UserProgress;

class AchievementService
{
    public function grantByProgress(User $user, UserProgress $progress): array
    {
        $targetCodes = [];

        if ($progress->completed_tasks_count >= 1) {
            $targetCodes[] = 'first_task';
        }
        if ($progress->current_streak_days >= 7) {
            $targetCodes[] = 'streak_7';
        }
        if ($progress->current_streak_days >= 30) {
            $targetCodes[] = 'streak_30';
        }
        if ($progress->completed_tasks_count >= 100) {
            $targetCodes[] = 'task_100';
        }
        if ($progress->level >= 5) {
            $targetCodes[] = 'level_5';
        }

        $awarded = [];
        foreach ($targetCodes as $code) {
            $badge = AchievementBadge::where('code', $code)->first();
            if (!$badge) {
                continue;
            }

            $exists = UserAchievementBadge::where('user_id', $user->id)
                ->where('achievement_badge_id', $badge->id)
                ->exists();

            if ($exists) {
                continue;
            }

            UserAchievementBadge::create([
                'user_id' => $user->id,
                'achievement_badge_id' => $badge->id,
                'awarded_at' => now(),
            ]);

            $awarded[] = $code;
        }

        return $awarded;
    }
}
