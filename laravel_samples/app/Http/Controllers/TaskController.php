<?php

namespace App\Http\Controllers;

use App\Models\Task;
use App\Services\TaskCompletionService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class TaskController extends Controller
{
    public function complete(Request $request, Task $task, TaskCompletionService $completionService): JsonResponse
    {
        abort_unless($task->user_id === $request->user()->id, 403);

        $result = $completionService->complete($task, $request->user());

        return response()->json($result);
    }
}
