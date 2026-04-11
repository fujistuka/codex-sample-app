<?php

namespace Database\Seeders;

use App\Models\AchievementBadge;
use Illuminate\Database\Seeder;

class AchievementBadgeSeeder extends Seeder
{
    public function run(): void
    {
        AchievementBadge::upsert([
            ['code' => 'first_task', 'name' => 'はじめの一歩', 'description' => '初めてタスクを完了した'],
            ['code' => 'streak_7', 'name' => '7日継続', 'description' => '7日連続達成した'],
            ['code' => 'streak_30', 'name' => '30日継続', 'description' => '30日連続達成した'],
            ['code' => 'task_100', 'name' => '100タスク達成', 'description' => 'タスクを100件完了した'],
            ['code' => 'level_5', 'name' => 'レベル5到達', 'description' => 'レベル5に到達した'],
        ], ['code'], ['name', 'description']);
    }
}
