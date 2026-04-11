<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class TaskRewardLog extends Model
{
    protected $fillable = [
        'user_id', 'task_id', 'base_xp', 'streak_multiplier', 'streak_bonus_xp',
        'final_xp', 'streak_days_at_completion', 'applied_streak_bonus_key',
        'leveled_up', 'level_before', 'level_after', 'meta',
    ];

    protected $casts = [
        'leveled_up' => 'boolean',
        'meta' => 'array',
    ];
}
