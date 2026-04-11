<?php

namespace Tests\Feature;

use App\Models\Task;
use App\Models\User;
use App\Models\UserProgress;
use App\Services\TaskCompletionService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class TaskCompletionRewardTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_grants_xp_and_levels_up(): void
    {
        $user = User::factory()->create();
        $task = Task::factory()->create(['user_id' => $user->id, 'completed_at' => null]);

        UserProgress::create([
            'user_id' => $user->id,
            'total_xp' => 95,
            'level' => 1,
            'current_streak_days' => 2,
            'completed_tasks_count' => 0,
        ]);

        $result = app(TaskCompletionService::class)->complete($task, $user);

        $this->assertTrue($result['level']['leveled_up']);
        $this->assertSame(2, $result['level']['after']);
        $this->assertGreaterThanOrEqual(100, UserProgress::where('user_id', $user->id)->first()->total_xp);
    }
}
