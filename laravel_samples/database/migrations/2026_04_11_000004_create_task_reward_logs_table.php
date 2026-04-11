<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('task_reward_logs', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->foreignId('task_id')->constrained()->cascadeOnDelete();
            $table->unsignedInteger('base_xp');
            $table->decimal('streak_multiplier', 4, 2);
            $table->unsignedInteger('streak_bonus_xp');
            $table->unsignedInteger('final_xp');
            $table->unsignedInteger('streak_days_at_completion');
            $table->string('applied_streak_bonus_key')->nullable();
            $table->boolean('leveled_up')->default(false);
            $table->unsignedInteger('level_before');
            $table->unsignedInteger('level_after');
            $table->json('meta')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('task_reward_logs');
    }
};
