from __future__ import annotations

from dataclasses import dataclass
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

RECOMMENDED_CATEGORIES: Dict[str, List[str]] = {
    "生活": ["料理", "掃除", "休息"],
    "仕事": ["業務遂行", "準備", "反省・分析"],
    "勉強": ["AI", "自己開発", "学習", "動画", "カンファレンス"],
    "健康": ["運動", "睡眠"],
}

GROWTH_STAGES = (
    ("initial", "丁寧で応援中心"),
    ("middle", "フレンドリーに挑戦"),
    ("late", "少し頼りつつ成長実感"),
    ("partner", "一緒に進む相棒"),
)

GROWTH_EVENT_BADGES = {
    "streak_7": "confidence_step",
    "challenge_mission_1": "challenge_first_step",
    "streak_30": "confidence_breakthrough",
}


def _build_badges() -> List[Dict[str, object]]:
    badges: List[Dict[str, object]] = []

    def add(code: str, name: str, icon: str, description: str, category: str, metric: str, target: int) -> None:
        badges.append(
            {
                "code": code,
                "name": name,
                "icon": icon,
                "description": description,
                "category": category,
                "metric": metric,
                "target": target,
            }
        )

    # 継続（5）
    for days, label in [(3, "3日"), (7, "1週間"), (14, "2週間"), (30, "30日"), (60, "60日")]:
        add(f"streak_{days}", f"継続{label}", "🔥", f"{days}日以上連続で達成する", "継続", "streak_days", days)

    # ミッション達成（5）
    for cnt in [1, 3, 5, 10, 20]:
        add(
            f"mission_{cnt}",
            f"ミッション達成{cnt}",
            "🎯",
            f"デイリーミッションを{cnt}回達成する",
            "ミッション",
            "mission_completed_count",
            cnt,
        )

    # challengeミッション（2）
    for cnt in [1, 5]:
        add(
            f"challenge_mission_{cnt}",
            f"Challenge挑戦{cnt}",
            "⚡",
            f"challenge難易度ミッションを{cnt}回達成する",
            "ミッション",
            "challenge_mission_completed_count",
            cnt,
        )

    # 累積タスク（5）
    for cnt in [5, 10, 25, 50, 100]:
        add(
            f"completed_{cnt}",
            f"完了タスク{cnt}",
            "✅",
            f"タスクを累積{cnt}件完了する",
            "累積",
            "completed_tasks",
            cnt,
        )

    # レベル（5）
    for lv in [2, 3, 5, 8, 10]:
        add(
            f"level_{lv}",
            f"レベル{lv}到達",
            "⭐",
            f"レベル{lv}に到達する",
            "累積",
            "level",
            lv,
        )

    # XP（3）
    for xp in [100, 300, 600]:
        add(
            f"xp_{xp}",
            f"累積XP {xp}",
            "💠",
            f"累積XPを{xp}以上にする",
            "累積",
            "total_xp",
            xp,
        )

    # カテゴリ誘導（5）
    for code, display in [
        ("category_life_5", "生活を5件完了"),
        ("category_work_5", "仕事を5件完了"),
        ("category_study_5", "勉強を5件完了"),
        ("category_health_5", "健康を5件完了"),
        ("category_balance_4", "4カテゴリ達成"),
    ]:
        if code == "category_balance_4":
            add(code, display, "🧭", "4カテゴリそれぞれで1件以上完了する", "カテゴリ", "category_balance_count", 4)
        else:
            metric = {
                "category_life_5": "category_life_completed",
                "category_work_5": "category_work_completed",
                "category_study_5": "category_study_completed",
                "category_health_5": "category_health_completed",
            }[code]
            add(code, display, "📚", f"{display}こと", "カテゴリ", metric, 5)

    return badges


BADGE_DEFINITIONS = _build_badges()  # 30件
BADGE_BY_CODE = {badge["code"]: badge for badge in BADGE_DEFINITIONS}

DAILY_MISSION_REWARDS = {
    "easy": 15,
    "normal": 30,
    "challenge": 50,
}

DAILY_MISSION_LIBRARY = {
    "easy": [
        {"id": "create_1", "title": "タスクを1件追加する", "description": "今日やることを1つ書き出そう。", "objective": {"kind": "created_today", "target": 1}},
        {"id": "complete_1", "title": "タスクを1件完了する", "description": "小さな完了を1つ積み上げよう。", "objective": {"kind": "completed_today", "target": 1}},
        {"id": "study_1", "title": "勉強カテゴリを1件進める", "description": "苦手でも1つ触ってみよう。", "objective": {"kind": "category_completed_today", "target": 1, "category": "勉強"}},
    ],
    "normal": [
        {"id": "create_2", "title": "タスクを2件追加する", "description": "今日進めたい項目を2つ用意しよう。", "objective": {"kind": "created_today", "target": 2}},
        {"id": "complete_2", "title": "タスクを2件完了する", "description": "勢いよく2つ片付けよう。", "objective": {"kind": "completed_today", "target": 2}},
        {"id": "priority_complete_1", "title": "優先度「高」のタスクを1件完了する", "description": "重要タスクを先に片付けよう。", "objective": {"kind": "high_priority_completed_today", "target": 1}},
    ],
    "challenge": [
        {"id": "complete_3", "title": "タスクを3件完了する", "description": "集中して3つ完了を目指そう。", "objective": {"kind": "completed_today", "target": 3}},
        {"id": "priority_complete_2", "title": "優先度「高」のタスクを2件完了する", "description": "重要タスクをまとめて進めよう。", "objective": {"kind": "high_priority_completed_today", "target": 2}},
        {"id": "study_2", "title": "勉強カテゴリを2件完了する", "description": "苦手を一歩ずつ克服しよう。", "objective": {"kind": "category_completed_today", "target": 2, "category": "勉強"}},
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


def evaluate_badges(metrics: Dict[str, int]) -> List[str]:
    earned: List[str] = []
    for badge in BADGE_DEFINITIONS:
        metric = str(badge["metric"])
        target = int(badge["target"])
        current = int(metrics.get(metric, 0))
        if current >= target:
            earned.append(str(badge["code"]))
    return earned


def badge_progress(metrics: Dict[str, int], earned_codes: List[str]) -> List[Dict[str, object]]:
    earned_set = set(earned_codes)
    items: List[Dict[str, object]] = []
    for badge in BADGE_DEFINITIONS:
        metric = str(badge["metric"])
        target = int(badge["target"])
        current = int(metrics.get(metric, 0))
        items.append(
            {
                "code": badge["code"],
                "name": badge["name"],
                "icon": badge["icon"],
                "description": badge["description"],
                "category": badge["category"],
                "target": target,
                "current": min(current, target),
                "earned": badge["code"] in earned_set,
            }
        )
    return items


def character_growth_stage(metrics: Dict[str, int]) -> Tuple[str, str]:
    growth_score = int(metrics.get("earned_badges", 0)) + int(metrics.get("mission_completed_count", 0))
    if growth_score >= 35:
        return ("partner", "相棒")
    if growth_score >= 18:
        return ("late", "後期")
    if growth_score >= 8:
        return ("middle", "中期")
    return ("initial", "初期")


def character_event_payload(summary: Dict[str, object]) -> Dict[str, object]:
    return {
        "event_type": "task_rewarded",
        "leveled_up": summary.get("leveled_up", False),
        "new_badges": summary.get("new_badges", []),
        "gained_xp": summary.get("gained_xp", 0),
        "streak_days": summary.get("streak_days", 1),
    }
