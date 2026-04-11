<?php

namespace App\Services;

use Carbon\Carbon;

class StreakService
{
    public function calculateNextStreak(?Carbon $lastCompletedOn, int $currentStreakDays, Carbon $today): int
    {
        if (!$lastCompletedOn) {
            return 1;
        }

        if ($lastCompletedOn->isSameDay($today)) {
            return $currentStreakDays;
        }

        if ($lastCompletedOn->copy()->addDay()->isSameDay($today)) {
            return $currentStreakDays + 1;
        }

        return 1;
    }

    public function resolveBonusXp(int $streakDays): int
    {
        foreach (config('gamification.streak_bonus') as $threshold => $bonus) {
            if ($streakDays >= (int) $threshold) {
                return (int) $bonus;
            }
        }

        return 0;
    }

    public function resolveMultiplier(int $streakDays): float
    {
        foreach (config('gamification.streak_multiplier') as $rule) {
            if ($streakDays >= $rule['min'] && (is_null($rule['max']) || $streakDays <= $rule['max'])) {
                return (float) $rule['multiplier'];
            }
        }

        return 1.0;
    }
}
