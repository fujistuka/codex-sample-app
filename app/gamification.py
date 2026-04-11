from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

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
    ("first_task", "初めてタスクを完了した"),
    ("streak_7", "7日連続達成した"),
    ("streak_30", "30日連続達成した"),
    ("task_100", "タスクを100件完了した"),
    ("level_5", "レベル5に到達した"),
]


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


def calculate_next_streak(last_completed_on: str | None, now_dt: datetime) -> int:
    if not last_completed_on:
        return 1

    last_date = datetime.fromisoformat(last_completed_on).date()
    now_date = now_dt.date()
    diff_days = (now_date - last_date).days

    if diff_days <= 0:
        return 1
    if diff_days == 1:
        return None  # caller should increment existing
    return 1


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
