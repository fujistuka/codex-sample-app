<?php

namespace App\Services;

class LevelService
{
    public function levelFromXp(int $xp): int
    {
        $xpPerLevel = (int) config('gamification.level.xp_per_level', 100);
        return intdiv($xp, $xpPerLevel) + 1;
    }

    public function detectLevelUp(int $beforeXp, int $afterXp): array
    {
        $before = $this->levelFromXp($beforeXp);
        $after = $this->levelFromXp($afterXp);

        return [
            'before' => $before,
            'after' => $after,
            'leveled_up' => $after > $before,
        ];
    }
}
