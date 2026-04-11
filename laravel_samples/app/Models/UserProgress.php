<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class UserProgress extends Model
{
    protected $fillable = [
        'user_id', 'total_xp', 'level', 'current_streak_days',
        'longest_streak_days', 'last_completed_on', 'completed_tasks_count',
    ];

    protected $casts = [
        'last_completed_on' => 'date',
    ];

    public function user()
    {
        return $this->belongsTo(User::class);
    }
}
