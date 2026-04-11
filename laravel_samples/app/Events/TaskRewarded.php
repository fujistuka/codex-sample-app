<?php

namespace App\Events;

use App\Models\Task;
use App\Models\User;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class TaskRewarded
{
    use Dispatchable, SerializesModels;

    public function __construct(
        public User $user,
        public Task $task,
        public array $xp,
        public array $level,
        public array $awardedBadges,
        public int $streakDays,
    ) {
    }
}
