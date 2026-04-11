<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class UserAchievementBadge extends Model
{
    protected $fillable = ['user_id', 'achievement_badge_id', 'awarded_at'];

    protected $casts = [
        'awarded_at' => 'datetime',
    ];
}
