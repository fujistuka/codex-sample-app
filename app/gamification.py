from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

BASE_XP = 10
LEVEL_XP_STEP = 100

STREAK_MULTIPLIERS = (
    (30, 1.5),
    (7, 1.2),
    (3, 1.1),
    (1, 1.0),
)

STREAK_BONUSES = (
    (30, 20),
    (7, 10),
    (3, 5),
)

BADGE_DEFINITIONS = [
    {"code": "first_task", "name": "初めてタスクを完了した", "icon": "🌱"},
    {"code": "streak_7", "name": "7日連続達成した", "icon": "🔥"},
    {"code": "streak_30", "name": "30日連続達成した", "icon": "🏆"},
    {"code": "task_100", "name": "タスクを100件完了した", "icon": "💯"},
    {"code": "level_5", "name": "レベル5に到達した", "icon": "⭐"},
]

DAILY_MISSION_REWARDS = {
    "easy": 15,
    "normal": 30,
    "challenge": 50,
}

DAILY_MISSION_LIBRARY = {
    "easy": [
        {
            "id": "create_1",
            "title": "タスクを1件追加する",
            "description": "今日やることを1つ書き出そう。",
            "objective": {"kind": "created_today", "target": 1},
        },
        {
            "id": "complete_1",
            "title": "タスクを1件完了する",
            "description": "小さな完了を1つ積み上げよう。",
            "objective": {"kind": "completed_today", "target": 1},
        },
        {
            "id": "active_2",
            "title": "未完了タスクを2件まで整理する",
            "description": "抱えているタスク数を軽くしよう。",
            "objective": {"kind": "active_todos_lte", "target": 2},
        },
    ],
    "normal": [
        {
            "id": "create_2",
            "title": "タスクを2件追加する",
            "description": "今日進めたい項目を2つ用意しよう。",
            "objective": {"kind": "created_today", "target": 2},
        },
        {
            "id": "complete_2",
            "title": "タスクを2件完了する",
            "description": "勢いよく2つ片付けよう。",
            "objective": {"kind": "completed_today", "target": 2},
        },
        {
            "id": "priority_complete_1",
            "title": "優先度「高」のタスクを1件完了する",
            "description": "重要タスクを先に片付けよう。",
            "objective": {"kind": "high_priority_completed_today", "target": 1},
        },
    ],
    "challenge": [
        {
            "id": "complete_3",
            "title": "タスクを3件完了する",
            "description": "集中して3つ完了を目指そう。",
            "objective": {"kind": "completed_today", "target": 3},
        },
        {
            "id": "priority_complete_2",
            "title": "優先度「高」のタスクを2件完了する",
            "description": "重要タスクをまとめて進めよう。",
            "objective": {"kind": "high_priority_completed_today", "target": 2},
        },
        {
            "id": "active_0",
            "title": "未完了タスクを0件にする",
            "description": "今日の未完了をゼロにしよう。",
            "objective": {"kind": "active_todos_lte", "target": 0},
        },
    ],
}


@dataclass
class RewardBreakdown:
    base_xp: int
    multiplier: float
    streak_bonus: int
    gained_xp: int


def level_from_total_xp(total_xp: int) -> int:
    return total_xp // LEVEL_XP_STEP + 1


def xp_to_next_level(total_xp: int) -> int:
    return LEVEL_XP_STEP - (total_xp % LEVEL_XP_STEP)


def streak_multiplier(streak_days: int) -> float:
    for min_days, value in STREAK_MULTIPLIERS:
        if streak_days >= min_days:
            return value
    return 1.0


def streak_bonus(streak_days: int) -> int:
    for min_days, bonus in STREAK_BONUSES:
        if streak_days >= min_days:
            return bonus
    return 0


def calculate_reward(streak_days: int, base_xp: int = BASE_XP) -> RewardBreakdown:
    multiplier = streak_multiplier(streak_days)
    bonus = streak_bonus(streak_days)
    gained = int(base_xp * multiplier) + bonus
    return RewardBreakdown(base_xp=base_xp, multiplier=multiplier, streak_bonus=bonus, gained_xp=gained)


def evaluate_badges(total_completed: int, streak_days: int, level: int) -> List[str]:
    badges: List[str] = []
    if total_completed >= 1:
        badges.append("first_task")
    if streak_days >= 7:
        badges.append("streak_7")
    if streak_days >= 30:
        badges.append("streak_30")
    if total_completed >= 100:
        badges.append("task_100")
    if level >= 5:
        badges.append("level_5")
    return badges


def character_event_payload(summary: Dict[str, object]) -> Dict[str, object]:
    return {
        "event_type": "task_rewarded",
        "leveled_up": summary.get("leveled_up", False),
        "new_badges": summary.get("new_badges", []),
        "gained_xp": summary.get("gained_xp", 0),
        "streak_days": summary.get("streak_days", 1),
    }
