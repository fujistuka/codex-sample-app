<?php

namespace App\Services;

class RewardService
{
    public function __construct(private StreakService $streakService)
    {
    }

    public function calculate(int $streakDays, int $baseXp = null): array
    {
        $baseXp = $baseXp ?? (int) config('gamification.base_xp', 10);
        $multiplier = $this->streakService->resolveMultiplier($streakDays);
        $bonus = $this->streakService->resolveBonusXp($streakDays);

        $finalXp = (int) floor($baseXp * $multiplier) + $bonus;

        return [
            'base_xp' => $baseXp,
            'multiplier' => $multiplier,
            'streak_bonus_xp' => $bonus,
            'final_xp' => $finalXp,
        ];
    }
}
