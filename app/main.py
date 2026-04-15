import json
import os
import re
import secrets
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse
from app.gamification import (
    BADGE_DEFINITIONS,
    BASE_XP,
    DAILY_MISSION_LIBRARY,
    DAILY_MISSION_REWARDS,
    calculate_reward,
    character_event_payload,
    evaluate_badges,
    level_from_total_xp,
    xp_to_next_level,
)

try:
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # fallback for restricted/offline environments
    FastAPI = None
    Header = None
    HTTPException = Exception
    CORSMiddleware = None
    FileResponse = None
    StaticFiles = None
    BaseModel = object
    Field = lambda default=None, **kwargs: default  # noqa: E731

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB_PATH = BASE_DIR / "data" / "todo.db"
DB_PATH = Path(os.getenv("TODO_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "password"
SESSION_DAYS = 30

sessions: Dict[str, int] = {}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                due_date TEXT,
                priority INTEGER NOT NULL DEFAULT 2,
                tags TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id INTEGER PRIMARY KEY,
                total_xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                streak_days INTEGER NOT NULL DEFAULT 0,
                last_completed_on TEXT,
                completed_tasks INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS achievement_master (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT NOT NULL DEFAULT '🏅'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER NOT NULL,
                achievement_code TEXT NOT NULL,
                awarded_at TEXT NOT NULL,
                PRIMARY KEY (user_id, achievement_code),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (achievement_code) REFERENCES achievement_master(code)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reward_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                todo_id INTEGER NOT NULL,
                gained_xp INTEGER NOT NULL,
                base_xp INTEGER NOT NULL,
                multiplier REAL NOT NULL,
                streak_bonus INTEGER NOT NULL,
                streak_days INTEGER NOT NULL,
                total_xp_after INTEGER NOT NULL,
                level_after INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (todo_id) REFERENCES todos(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS completion_history (
                user_id INTEGER NOT NULL,
                completed_on TEXT NOT NULL,
                PRIMARY KEY(user_id, completed_on),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_activity (
                user_id INTEGER PRIMARY KEY,
                last_login_on TEXT,
                login_streak_days INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_missions (
                user_id INTEGER NOT NULL,
                mission_date TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                candidates_json TEXT NOT NULL,
                selected_mission_id TEXT,
                selected_mission_json TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                reward_xp INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, mission_date),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        user = conn.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_USERNAME,)).fetchone()
        if user is None:
            conn.execute(
                "INSERT INTO users(username, password) VALUES (?, ?)",
                (DEFAULT_USERNAME, DEFAULT_PASSWORD),
            )
            user = conn.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_USERNAME,)).fetchone()

        conn.execute(
            """
            INSERT OR IGNORE INTO user_progress(user_id, total_xp, level, streak_days, last_completed_on, completed_tasks, updated_at)
            VALUES (?, 0, 1, 0, NULL, 0, ?)
            """,
            (int(user["id"]), iso_now()),
        )

        columns = [r["name"] for r in conn.execute("PRAGMA table_info(achievement_master)").fetchall()]
        if "icon" not in columns:
            conn.execute("ALTER TABLE achievement_master ADD COLUMN icon TEXT NOT NULL DEFAULT '🏅'")

        for badge in BADGE_DEFINITIONS:
            conn.execute(
                "INSERT OR IGNORE INTO achievement_master(code, name, icon) VALUES (?, ?, ?)",
                (badge["code"], badge["name"], badge["icon"]),
            )
            conn.execute(
                "UPDATE achievement_master SET name = ?, icon = ? WHERE code = ?",
                (badge["name"], badge["icon"], badge["code"]),
            )


def iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def row_to_todo(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "id": row["id"],
        "title": row["title"],
        "completed": bool(row["completed"]),
        "due_date": row["due_date"],
        "priority": row["priority"],
        "tags": [tag.strip() for tag in row["tags"].split(",") if tag.strip()],
        "created_at": row["created_at"],
    }


def _today_str() -> str:
    return datetime.utcnow().date().isoformat()


def _normalize_difficulty(difficulty: str) -> str:
    if difficulty in DAILY_MISSION_LIBRARY:
        return difficulty
    return "normal"


def _build_daily_candidates(user_id: int, mission_date: str, difficulty: str) -> List[Dict[str, object]]:
    diff = _normalize_difficulty(difficulty)
    templates = DAILY_MISSION_LIBRARY[diff]
    day_seed = int(mission_date.replace("-", ""))
    ranked = sorted(
        templates,
        key=lambda item: ((hash(f"{user_id}:{mission_date}:{item['id']}") + day_seed) % 100000),
    )
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "description": item["description"],
            "objective": item["objective"],
            "reward_xp": DAILY_MISSION_REWARDS[diff],
        }
        for item in ranked[:3]
    ]


def _ensure_daily_mission(conn: sqlite3.Connection, user_id: int, mission_date: str, difficulty: str = "normal") -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT user_id, mission_date, difficulty, candidates_json, selected_mission_id, selected_mission_json,
               completed, completed_at, reward_xp
        FROM daily_missions
        WHERE user_id = ? AND mission_date = ?
        """,
        (user_id, mission_date),
    ).fetchone()
    if row is not None:
        return row

    safe_diff = _normalize_difficulty(difficulty)
    candidates = _build_daily_candidates(user_id, mission_date, safe_diff)
    conn.execute(
        """
        INSERT INTO daily_missions(
            user_id, mission_date, difficulty, candidates_json, selected_mission_id, selected_mission_json,
            completed, completed_at, reward_xp, updated_at
        ) VALUES (?, ?, ?, ?, NULL, NULL, 0, NULL, 0, ?)
        """,
        (user_id, mission_date, safe_diff, json.dumps(candidates, ensure_ascii=False), iso_now()),
    )
    return conn.execute(
        """
        SELECT user_id, mission_date, difficulty, candidates_json, selected_mission_id, selected_mission_json,
               completed, completed_at, reward_xp
        FROM daily_missions
        WHERE user_id = ? AND mission_date = ?
        """,
        (user_id, mission_date),
    ).fetchone()


def _today_metrics(conn: sqlite3.Connection, user_id: int, mission_date: str) -> Dict[str, int]:
    created_today = conn.execute(
        "SELECT COUNT(*) AS cnt FROM todos WHERE user_id = ? AND substr(created_at, 1, 10) = ?",
        (user_id, mission_date),
    ).fetchone()["cnt"]
    completed_today = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM reward_logs
        WHERE user_id = ? AND substr(created_at, 1, 10) = ?
        """,
        (user_id, mission_date),
    ).fetchone()["cnt"]
    high_priority_completed_today = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM reward_logs rl
        JOIN todos t ON t.id = rl.todo_id
        WHERE rl.user_id = ? AND substr(rl.created_at, 1, 10) = ? AND t.priority = 1
        """,
        (user_id, mission_date),
    ).fetchone()["cnt"]
    active_todos = conn.execute(
        "SELECT COUNT(*) AS cnt FROM todos WHERE user_id = ? AND completed = 0",
        (user_id,),
    ).fetchone()["cnt"]
    return {
        "created_today": int(created_today),
        "completed_today": int(completed_today),
        "high_priority_completed_today": int(high_priority_completed_today),
        "active_todos": int(active_todos),
    }


def _is_mission_completed(objective: Dict[str, object], metrics: Dict[str, int]) -> bool:
    kind = objective.get("kind")
    target = int(objective.get("target", 1))
    if kind == "created_today":
        return metrics["created_today"] >= target
    if kind == "completed_today":
        return metrics["completed_today"] >= target
    if kind == "high_priority_completed_today":
        return metrics["high_priority_completed_today"] >= target
    if kind == "active_todos_lte":
        return metrics["active_todos"] <= target
    return False


def _mission_row_to_payload(row: sqlite3.Row, metrics: Dict[str, int]) -> Dict[str, object]:
    candidates = json.loads(row["candidates_json"] or "[]")
    selected = json.loads(row["selected_mission_json"]) if row["selected_mission_json"] else None
    return {
        "date": row["mission_date"],
        "difficulty": row["difficulty"],
        "candidates": candidates,
        "selected_mission_id": row["selected_mission_id"],
        "selected_mission": selected,
        "completed": bool(row["completed"]),
        "completed_at": row["completed_at"],
        "reward_xp": int(row["reward_xp"]),
        "metrics": metrics,
    }


def get_daily_mission_state(user_id: int) -> Dict[str, object]:
    mission_date = _today_str()
    with get_conn() as conn:
        row = _ensure_daily_mission(conn, user_id, mission_date)
        metrics = _today_metrics(conn, user_id, mission_date)
    return _mission_row_to_payload(row, metrics)


def set_daily_mission_difficulty(user_id: int, difficulty: str) -> Dict[str, object]:
    mission_date = _today_str()
    safe_diff = _normalize_difficulty(difficulty)
    with get_conn() as conn:
        row = _ensure_daily_mission(conn, user_id, mission_date, safe_diff)
        if row["selected_mission_id"] is None:
            candidates = _build_daily_candidates(user_id, mission_date, safe_diff)
            conn.execute(
                """
                UPDATE daily_missions
                SET difficulty = ?, candidates_json = ?, updated_at = ?
                WHERE user_id = ? AND mission_date = ?
                """,
                (safe_diff, json.dumps(candidates, ensure_ascii=False), iso_now(), user_id, mission_date),
            )
        row = _ensure_daily_mission(conn, user_id, mission_date, safe_diff)
        metrics = _today_metrics(conn, user_id, mission_date)
    payload = _mission_row_to_payload(row, metrics)
    payload["difficulty_message"] = {
        "easy": "今日は軽めにいこう。できる範囲でOK！",
        "normal": "ちょうどいい目標で、安定して進めよう！",
        "challenge": "チャレンジいいね！一緒に達成を狙おう🔥",
    }[safe_diff]
    return payload


def select_daily_mission(user_id: int, mission_id: str) -> Dict[str, object]:
    mission_date = _today_str()
    with get_conn() as conn:
        row = _ensure_daily_mission(conn, user_id, mission_date)
        candidates = json.loads(row["candidates_json"] or "[]")
        if row["selected_mission_id"]:
            selected = row["selected_mission_id"]
            if selected != mission_id:
                raise ValueError("本日のミッションはすでに選択済みです")
        chosen = next((c for c in candidates if c["id"] == mission_id), None)
        if chosen is None:
            raise ValueError("候補にないミッションです")
        conn.execute(
            """
            UPDATE daily_missions
            SET selected_mission_id = ?, selected_mission_json = ?, updated_at = ?
            WHERE user_id = ? AND mission_date = ?
            """,
            (mission_id, json.dumps(chosen, ensure_ascii=False), iso_now(), user_id, mission_date),
        )
        updated = _ensure_daily_mission(conn, user_id, mission_date)
        metrics = _today_metrics(conn, user_id, mission_date)
    return _mission_row_to_payload(updated, metrics)


def evaluate_daily_mission(user_id: int) -> Optional[Dict[str, object]]:
    mission_date = _today_str()
    with get_conn() as conn:
        row = _ensure_daily_mission(conn, user_id, mission_date)
        if not row["selected_mission_json"] or int(row["completed"]) == 1:
            return None
        selected = json.loads(row["selected_mission_json"])
        metrics = _today_metrics(conn, user_id, mission_date)
        if not _is_mission_completed(selected.get("objective", {}), metrics):
            return None

        reward_xp = int(selected.get("reward_xp") or DAILY_MISSION_REWARDS.get(row["difficulty"], 30))
        progress = _load_progress(conn, user_id)
        prev_level = int(progress["level"])
        new_total = int(progress["total_xp"]) + reward_xp
        new_level = level_from_total_xp(new_total)
        conn.execute(
            """
            UPDATE user_progress
            SET total_xp = ?, level = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (new_total, new_level, iso_now(), user_id),
        )
        conn.execute(
            """
            UPDATE daily_missions
            SET completed = 1, completed_at = ?, reward_xp = ?, updated_at = ?
            WHERE user_id = ? AND mission_date = ?
            """,
            (iso_now(), reward_xp, iso_now(), user_id, mission_date),
        )
    return {
        "mission_completed": True,
        "mission": selected,
        "reward_xp": reward_xp,
        "leveled_up": new_level > prev_level,
        "total_xp": new_total,
        "level": new_level,
        "xp_to_next_level": xp_to_next_level(new_total),
    }


def _load_progress(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT user_id, total_xp, level, streak_days, last_completed_on, completed_tasks, updated_at
        FROM user_progress WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO user_progress(user_id, total_xp, level, streak_days, last_completed_on, completed_tasks, updated_at)
            VALUES (?, 0, 1, 0, NULL, 0, ?)
            """,
            (user_id, iso_now()),
        )
        row = conn.execute(
            "SELECT user_id, total_xp, level, streak_days, last_completed_on, completed_tasks, updated_at FROM user_progress WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row


def get_progress(user_id: int) -> Dict[str, object]:
    with get_conn() as conn:
        row = _load_progress(conn, user_id)
        badges = conn.execute(
            """
            SELECT ua.achievement_code AS code, am.name, am.icon, ua.awarded_at
            FROM user_achievements ua
            JOIN achievement_master am ON am.code = ua.achievement_code
            WHERE ua.user_id = ?
            ORDER BY ua.awarded_at DESC
            """,
            (user_id,),
        ).fetchall()
        total_badges = conn.execute("SELECT COUNT(*) AS cnt FROM achievement_master").fetchone()["cnt"]
        achieved_dates = conn.execute(
            """
            SELECT completed_on
            FROM completion_history
            WHERE user_id = ?
            ORDER BY completed_on DESC
            LIMIT 90
            """,
            (user_id,),
        ).fetchall()
        login_row = conn.execute(
            "SELECT login_streak_days, last_login_on FROM login_activity WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    total_xp = int(row["total_xp"])
    current_level = int(row["level"])
    login_streak_days = int(login_row["login_streak_days"]) if login_row else 0
    last_login_on = login_row["last_login_on"] if login_row else None
    return {
        "total_xp": total_xp,
        "level": current_level,
        "streak_days": int(row["streak_days"]),
        "completed_tasks": int(row["completed_tasks"]),
        "login_streak_days": login_streak_days,
        "last_login_on": last_login_on,
        "xp_to_next_level": xp_to_next_level(total_xp),
        "badges": [{"code": b["code"], "name": b["name"], "icon": b["icon"], "awarded_at": b["awarded_at"]} for b in badges],
        "badge_summary": {"earned": len(badges), "total": int(total_badges)},
        "achievement_dates": [r["completed_on"] for r in achieved_dates],
    }


def _period_start(days: int) -> str:
    safe_days = max(1, min(days, 366))
    start_date = datetime.utcnow().date() - timedelta(days=safe_days - 1)
    return start_date.isoformat()


def _review_comment(metrics: Dict[str, object]) -> str:
    streak_days = int(metrics.get("active_days", 0))
    mission_count = int(metrics.get("daily_missions_completed", 0))
    xp = int(metrics.get("gained_xp", 0))
    completed = int(metrics.get("completed_tasks", 0))
    if streak_days >= 5:
        return "今週はすごく安定して続けられたね！このリズムは大きな力だよ。"
    if mission_count >= 3:
        return "デイリーミッションをしっかり達成できてる！目標選びが上手だね。"
    if completed >= 5 or xp >= 100:
        return "しっかり前進してるよ。積み重ねがちゃんと結果になってる！"
    if completed == 0 and mission_count == 0:
        return "今週はおつかれさま。来週は小さな1歩から一緒に再開しよう。"
    return "コツコツ進められているよ。来週はもう一段だけ目標を上げてみよう！"


def get_review_summary(user_id: int, days: int = 7) -> Dict[str, object]:
    period_days = max(1, min(days, 366))
    start_date = _period_start(period_days)
    end_date = _today_str()

    with get_conn() as conn:
        created_tasks = int(
            conn.execute(
                "SELECT COUNT(*) AS cnt FROM todos WHERE user_id = ? AND substr(created_at, 1, 10) >= ?",
                (user_id, start_date),
            ).fetchone()["cnt"]
        )
        completed_tasks = int(
            conn.execute(
                "SELECT COUNT(*) AS cnt FROM reward_logs WHERE user_id = ? AND substr(created_at, 1, 10) >= ?",
                (user_id, start_date),
            ).fetchone()["cnt"]
        )
        daily_missions_completed = int(
            conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM daily_missions
                WHERE user_id = ? AND completed = 1 AND mission_date >= ?
                """,
                (user_id, start_date),
            ).fetchone()["cnt"]
        )
        task_xp = int(
            conn.execute(
                "SELECT COALESCE(SUM(gained_xp), 0) AS total FROM reward_logs WHERE user_id = ? AND substr(created_at, 1, 10) >= ?",
                (user_id, start_date),
            ).fetchone()["total"]
        )
        mission_xp = int(
            conn.execute(
                """
                SELECT COALESCE(SUM(reward_xp), 0) AS total
                FROM daily_missions
                WHERE user_id = ? AND completed = 1 AND mission_date >= ?
                """,
                (user_id, start_date),
            ).fetchone()["total"]
        )
        tag_rows = conn.execute(
            """
            SELECT tags FROM todos
            WHERE user_id = ? AND substr(created_at, 1, 10) >= ?
            """,
            (user_id, start_date),
        ).fetchall()
        active_date_rows = conn.execute(
            """
            SELECT d, COUNT(*) AS cnt FROM (
              SELECT substr(created_at, 1, 10) AS d FROM todos WHERE user_id = ? AND substr(created_at, 1, 10) >= ?
              UNION ALL
              SELECT substr(created_at, 1, 10) AS d FROM reward_logs WHERE user_id = ? AND substr(created_at, 1, 10) >= ?
              UNION ALL
              SELECT mission_date AS d FROM daily_missions WHERE user_id = ? AND completed = 1 AND mission_date >= ?
            ) tmp
            GROUP BY d
            ORDER BY d DESC
            """,
            (user_id, start_date, user_id, start_date, user_id, start_date),
        ).fetchall()

    tag_counter: Counter[str] = Counter()
    for row in tag_rows:
        raw = row["tags"] or ""
        tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        tag_counter.update(tags)
    top_tag = tag_counter.most_common(1)[0][0] if tag_counter else None
    active_days = len(active_date_rows)
    gained_xp = task_xp + mission_xp
    metrics = {
        "completed_tasks": completed_tasks,
        "created_tasks": created_tasks,
        "daily_missions_completed": daily_missions_completed,
        "gained_xp": gained_xp,
        "task_xp": task_xp,
        "mission_xp": mission_xp,
        "active_days": active_days,
        "top_tag": top_tag,
    }
    return {
        "period": {"days": period_days, "start_date": start_date, "end_date": end_date},
        "metrics": metrics,
        "activity_dates": [row["d"] for row in active_date_rows],
        "character_comment": _review_comment(metrics),
    }


def grant_completion_reward(user_id: int, todo_id: int) -> Dict[str, object]:
    now = datetime.utcnow()
    today = now.date()

    with get_conn() as conn:
        progress = _load_progress(conn, user_id)
        prev_total_xp = int(progress["total_xp"])
        prev_level = int(progress["level"])
        prev_streak = int(progress["streak_days"])
        last_completed_on = progress["last_completed_on"]

        streak_days = 1
        if last_completed_on:
            last_date = datetime.fromisoformat(last_completed_on).date()
            diff_days = (today - last_date).days
            if diff_days == 1:
                streak_days = prev_streak + 1
            elif diff_days <= 0:
                streak_days = max(prev_streak, 1)

        reward = calculate_reward(streak_days=streak_days, base_xp=BASE_XP)
        new_total_xp = prev_total_xp + reward.gained_xp
        new_level = level_from_total_xp(new_total_xp)
        completed_tasks = int(progress["completed_tasks"]) + 1

        conn.execute(
            """
            UPDATE user_progress
            SET total_xp = ?, level = ?, streak_days = ?, last_completed_on = ?, completed_tasks = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (new_total_xp, new_level, streak_days, today.isoformat(), completed_tasks, iso_now(), user_id),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO completion_history(user_id, completed_on)
            VALUES (?, ?)
            """,
            (user_id, today.isoformat()),
        )

        badge_codes = evaluate_badges(completed_tasks, streak_days, new_level)
        new_badges: List[Dict[str, str]] = []
        for code in badge_codes:
            awarded_at = iso_now()
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO user_achievements(user_id, achievement_code, awarded_at)
                VALUES (?, ?, ?)
                """,
                (user_id, code, awarded_at),
            )
            if cur.rowcount > 0:
                name_row = conn.execute("SELECT name FROM achievement_master WHERE code = ?", (code,)).fetchone()
                new_badges.append({"code": code, "name": name_row["name"] if name_row else code, "awarded_at": awarded_at})

        conn.execute(
            """
            INSERT INTO reward_logs(
                user_id, todo_id, gained_xp, base_xp, multiplier, streak_bonus, streak_days, total_xp_after, level_after, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                todo_id,
                reward.gained_xp,
                reward.base_xp,
                reward.multiplier,
                reward.streak_bonus,
                streak_days,
                new_total_xp,
                new_level,
                iso_now(),
            ),
        )

    summary = {
        "gained_xp": reward.gained_xp,
        "base_xp": reward.base_xp,
        "multiplier": reward.multiplier,
        "streak_bonus": reward.streak_bonus,
        "streak_days": streak_days,
        "total_xp": new_total_xp,
        "level": new_level,
        "xp_to_next_level": xp_to_next_level(new_total_xp),
        "leveled_up": new_level > prev_level,
        "new_badges": new_badges,
    }
    summary["character_event"] = character_event_payload(summary)
    return summary


def verify_login(username: str, password: str) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
        return int(row["id"]) if row else None


def record_login_activity(user_id: int) -> None:
    today = datetime.utcnow().date()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_login_on, login_streak_days FROM login_activity WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO login_activity(user_id, last_login_on, login_streak_days, updated_at)
                VALUES (?, ?, 1, ?)
                """,
                (user_id, today.isoformat(), iso_now()),
            )
            return

        last_login_on = row["last_login_on"]
        streak = int(row["login_streak_days"])
        if last_login_on:
            last_date = datetime.fromisoformat(last_login_on).date()
            diff_days = (today - last_date).days
            if diff_days == 1:
                streak += 1
            elif diff_days > 1:
                streak = 1
        else:
            streak = 1

        conn.execute(
            """
            UPDATE login_activity
            SET last_login_on = ?, login_streak_days = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (today.isoformat(), streak, iso_now(), user_id),
        )


def create_session(user_id: int) -> str:
    token = secrets.token_hex(24)
    expires_at = (datetime.utcnow() + timedelta(days=SESSION_DAYS)).replace(microsecond=0).isoformat() + "Z"
    sessions[token] = user_id
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions(token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def user_id_from_token(authorization: Optional[str]) -> Optional[int]:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "", 1).strip()
    if token in sessions:
        return sessions[token]

    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return None

        expires_at = parse_iso(row["expires_at"])
        if expires_at < datetime.now(expires_at.tzinfo):
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None

        user_id = int(row["user_id"])
        sessions[token] = user_id
        return user_id


def validate_todo_payload(payload: Dict[str, object], partial: bool = False) -> Tuple[str, Optional[str], int, List[str]]:
    title = str(payload.get("title", "")).strip()
    due_date = payload.get("due_date")
    priority = payload.get("priority", 2)
    tags = payload.get("tags", [])

    if not partial or "title" in payload:
        if not title:
            raise ValueError("タイトルは必須です")

    if due_date in ("", None):
        due_date = None
    elif not isinstance(due_date, str):
        raise ValueError("期限日は文字列で指定してください")

    try:
        priority = int(priority)
    except (TypeError, ValueError) as exc:
        raise ValueError("優先度は1〜3の数値です") from exc

    if priority not in (1, 2, 3):
        raise ValueError("優先度は1〜3の数値です")

    if isinstance(tags, str):
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, list):
        tag_list = [str(t).strip() for t in tags if str(t).strip()]
    else:
        raise ValueError("タグは配列またはカンマ区切り文字列で指定してください")

    return title, due_date, priority, tag_list


def create_todo(user_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    title, due_date, priority, tags = validate_todo_payload(payload)
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO todos(user_id, title, completed, due_date, priority, tags, created_at)
            VALUES (?, ?, 0, ?, ?, ?, ?)
            """,
            (user_id, title, due_date, priority, ",".join(tags), iso_now()),
        )
        todo_id = cursor.lastrowid
        row = conn.execute(
            "SELECT id, title, completed, due_date, priority, tags, created_at FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        ).fetchone()
    todo = row_to_todo(row)
    mission_update = evaluate_daily_mission(user_id)
    if mission_update:
        todo["daily_mission"] = mission_update
    return todo


def list_todos(
    user_id: int,
    q: str = "",
    status: str = "all",
    sort_by: str = "created_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 10,
) -> Dict[str, object]:
    allowed_sort = {"created_at", "due_date", "priority"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"

    order = "ASC" if order.lower() == "asc" else "DESC"
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    clauses = ["user_id = ?"]
    params: List[object] = [user_id]

    if q.strip():
        clauses.append("(title LIKE ? OR tags LIKE ?)")
        keyword = f"%{q.strip()}%"
        params.extend([keyword, keyword])

    if status == "completed":
        clauses.append("completed = 1")
    elif status == "active":
        clauses.append("completed = 0")

    where_sql = " AND ".join(clauses)

    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS cnt FROM todos WHERE {where_sql}", params).fetchone()["cnt"]
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT id, title, completed, due_date, priority, tags, created_at
            FROM todos
            WHERE {where_sql}
            ORDER BY {sort_by} {order}, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    items = [row_to_todo(row) for row in rows]
    total_pages = max((total + page_size - 1) // page_size, 1)
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    }


def get_todo_for_user(user_id: int, todo_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, title, completed, due_date, priority, tags, created_at FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        ).fetchone()


def update_todo(user_id: int, todo_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    existing = get_todo_for_user(user_id, todo_id)
    if existing is None:
        raise LookupError("ToDoが見つかりません")

    base = row_to_todo(existing)
    merged = {
        "title": payload.get("title", base["title"]),
        "due_date": payload.get("due_date", base["due_date"]),
        "priority": payload.get("priority", base["priority"]),
        "tags": payload.get("tags", base["tags"]),
    }

    title, due_date, priority, tags = validate_todo_payload(merged, partial=True)

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE todos
            SET title = ?, due_date = ?, priority = ?, tags = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, due_date, priority, ",".join(tags), todo_id, user_id),
        )
        row = conn.execute(
            "SELECT id, title, completed, due_date, priority, tags, created_at FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        ).fetchone()
    return row_to_todo(row)


def toggle_todo(user_id: int, todo_id: int) -> Dict[str, object]:
    existing = get_todo_for_user(user_id, todo_id)
    if existing is None:
        raise LookupError("ToDoが見つかりません")

    completed = 0 if existing["completed"] else 1
    with get_conn() as conn:
        conn.execute(
            "UPDATE todos SET completed = ? WHERE id = ? AND user_id = ?",
            (completed, todo_id, user_id),
        )
        row = conn.execute(
            "SELECT id, title, completed, due_date, priority, tags, created_at FROM todos WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        ).fetchone()
    todo = row_to_todo(row)
    if completed == 1:
        todo["reward"] = grant_completion_reward(user_id, todo_id)
        mission_update = evaluate_daily_mission(user_id)
        if mission_update:
            todo["daily_mission"] = mission_update
    return todo


def delete_todo(user_id: int, todo_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id))
        return cur.rowcount > 0


init_db()

if FastAPI is not None:
    app = FastAPI(title="ToDo App MVP")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    class LoginRequest(BaseModel):
        username: str
        password: str

    class TodoCreateRequest(BaseModel):
        title: str
        due_date: Optional[str] = None
        priority: int = 2
        tags: Union[List[str], str, None] = Field(default_factory=list)

    class TodoUpdateRequest(BaseModel):
        title: Optional[str] = None
        due_date: Optional[str] = None
        priority: Optional[int] = None
        tags: Optional[Union[List[str], str]] = None

    class DailyMissionDifficultyRequest(BaseModel):
        difficulty: str

    class DailyMissionSelectRequest(BaseModel):
        mission_id: str

    def require_user(authorization: Optional[str]) -> int:
        user_id = user_id_from_token(authorization)
        if user_id is None:
            raise HTTPException(status_code=401, detail="認証が必要です")
        return user_id

    @app.get("/")
    def read_index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.post("/api/login")
    def login(payload: LoginRequest) -> Dict[str, object]:
        user_id = verify_login(payload.username, payload.password)
        if user_id is None:
            raise HTTPException(status_code=401, detail="ログインに失敗しました")
        record_login_activity(user_id)
        token = create_session(user_id)
        return {"token": token, "username": payload.username}

    @app.get("/api/me")
    def me(authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        return {"user_id": user_id, "username": DEFAULT_USERNAME}

    @app.get("/api/todos")
    def get_todos(
        q: str = "",
        status: str = "all",
        sort_by: str = "created_at",
        order: str = "desc",
        page: int = 1,
        page_size: int = 10,
        authorization: Optional[str] = Header(default=None),
    ) -> Dict[str, object]:
        user_id = require_user(authorization)
        return list_todos(user_id, q, status, sort_by, order, page, page_size)

    @app.get("/api/progress")
    def api_progress(authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        return get_progress(user_id)

    @app.get("/api/review")
    def api_review(days: int = 7, authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        return get_review_summary(user_id, days=days)

    @app.get("/api/daily-mission")
    def api_daily_mission(authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        return get_daily_mission_state(user_id)

    @app.post("/api/daily-mission/difficulty")
    def api_daily_mission_difficulty(
        payload: DailyMissionDifficultyRequest, authorization: Optional[str] = Header(default=None)
    ) -> Dict[str, object]:
        user_id = require_user(authorization)
        return set_daily_mission_difficulty(user_id, payload.difficulty)

    @app.post("/api/daily-mission/select")
    def api_daily_mission_select(
        payload: DailyMissionSelectRequest, authorization: Optional[str] = Header(default=None)
    ) -> Dict[str, object]:
        user_id = require_user(authorization)
        try:
            return select_daily_mission(user_id, payload.mission_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/todos")
    def post_todo(payload: TodoCreateRequest, authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        try:
            return create_todo(user_id, payload.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.put("/api/todos/{todo_id}")
    def put_todo(todo_id: int, payload: TodoUpdateRequest, authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        try:
            return update_todo(user_id, todo_id, payload.model_dump(exclude_unset=True))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.patch("/api/todos/{todo_id}/toggle")
    def patch_todo(todo_id: int, authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        try:
            return toggle_todo(user_id, todo_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.delete("/api/todos/{todo_id}")
    def remove_todo(todo_id: int, authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
        user_id = require_user(authorization)
        deleted = delete_todo(user_id, todo_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="ToDoが見つかりません")
        return {"ok": True}
else:
    app = None


class FallbackTodoHandler(BaseHTTPRequestHandler):
    todo_id_pattern = re.compile(r"^/api/todos/(\d+)$")
    todo_toggle_pattern = re.compile(r"^/api/todos/(\d+)/toggle$")

    def _json(self, status: int, payload: Dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _parse_json_body(self) -> Dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _read_user(self) -> Optional[int]:
        auth = self.headers.get("Authorization")
        return user_id_from_token(auth)

    def _serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")

        if path.startswith("/static/"):
            file_path = STATIC_DIR / path.removeprefix("/static/")
            if file_path.exists() and file_path.is_file():
                mime = "text/plain; charset=utf-8"
                if file_path.suffix == ".js":
                    mime = "application/javascript; charset=utf-8"
                elif file_path.suffix == ".css":
                    mime = "text/css; charset=utf-8"
                elif file_path.suffix == ".html":
                    mime = "text/html; charset=utf-8"
                elif file_path.suffix == ".svg":
                    mime = "image/svg+xml"
                elif file_path.suffix == ".png":
                    mime = "image/png"
                elif file_path.suffix in {".jpg", ".jpeg"}:
                    mime = "image/jpeg"
                elif file_path.suffix == ".webp":
                    mime = "image/webp"
                return self._serve_file(file_path, mime)
            return self._json(404, {"detail": "Not Found"})

        if path == "/api/me":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})
            return self._json(200, {"user_id": user_id, "username": DEFAULT_USERNAME})

        if path == "/api/todos":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})

            query = parse_qs(parsed.query)
            result = list_todos(
                user_id=user_id,
                q=query.get("q", [""])[0],
                status=query.get("status", ["all"])[0],
                sort_by=query.get("sort_by", ["created_at"])[0],
                order=query.get("order", ["desc"])[0],
                page=int(query.get("page", ["1"])[0]),
                page_size=int(query.get("page_size", ["10"])[0]),
            )
            return self._json(200, result)

        if path == "/api/progress":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})
            return self._json(200, get_progress(user_id))

        if path == "/api/review":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})
            query = parse_qs(parsed.query)
            try:
                days = int(query.get("days", ["7"])[0])
            except ValueError:
                days = 7
            return self._json(200, get_review_summary(user_id, days=days))

        if path == "/api/daily-mission":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})
            return self._json(200, get_daily_mission_state(user_id))

        return self._json(404, {"detail": "Not Found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/api/login":
            try:
                payload = self._parse_json_body()
                username = str(payload.get("username", ""))
                password = str(payload.get("password", ""))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._json(400, {"detail": "JSONが不正です"})

            user_id = verify_login(username, password)
            if user_id is None:
                return self._json(401, {"detail": "ログインに失敗しました"})

            record_login_activity(user_id)
            token = create_session(user_id)
            return self._json(200, {"token": token, "username": username})

        if path == "/api/todos":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})

            try:
                payload = self._parse_json_body()
                todo = create_todo(user_id, payload)
                return self._json(200, todo)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._json(400, {"detail": "JSONが不正です"})
            except ValueError as error:
                return self._json(400, {"detail": str(error)})

        if path == "/api/daily-mission/difficulty":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})
            try:
                payload = self._parse_json_body()
                difficulty = str(payload.get("difficulty", "normal"))
                return self._json(200, set_daily_mission_difficulty(user_id, difficulty))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._json(400, {"detail": "JSONが不正です"})

        if path == "/api/daily-mission/select":
            user_id = self._read_user()
            if user_id is None:
                return self._json(401, {"detail": "認証が必要です"})
            try:
                payload = self._parse_json_body()
                mission_id = str(payload.get("mission_id", "")).strip()
                if not mission_id:
                    return self._json(400, {"detail": "mission_idは必須です"})
                return self._json(200, select_daily_mission(user_id, mission_id))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._json(400, {"detail": "JSONが不正です"})
            except ValueError as error:
                return self._json(400, {"detail": str(error)})

        return self._json(404, {"detail": "Not Found"})

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        matched = self.todo_id_pattern.match(path)
        if not matched:
            return self._json(404, {"detail": "Not Found"})

        user_id = self._read_user()
        if user_id is None:
            return self._json(401, {"detail": "認証が必要です"})

        todo_id = int(matched.group(1))
        try:
            payload = self._parse_json_body()
            updated = update_todo(user_id, todo_id, payload)
            return self._json(200, updated)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json(400, {"detail": "JSONが不正です"})
        except ValueError as error:
            return self._json(400, {"detail": str(error)})
        except LookupError as error:
            return self._json(404, {"detail": str(error)})

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        matched = self.todo_toggle_pattern.match(path)
        if not matched:
            return self._json(404, {"detail": "Not Found"})

        user_id = self._read_user()
        if user_id is None:
            return self._json(401, {"detail": "認証が必要です"})

        todo_id = int(matched.group(1))
        try:
            return self._json(200, toggle_todo(user_id, todo_id))
        except LookupError as error:
            return self._json(404, {"detail": str(error)})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        matched = self.todo_id_pattern.match(path)
        if not matched:
            return self._json(404, {"detail": "Not Found"})

        user_id = self._read_user()
        if user_id is None:
            return self._json(401, {"detail": "認証が必要です"})

        todo_id = int(matched.group(1))
        deleted = delete_todo(user_id, todo_id)
        if not deleted:
            return self._json(404, {"detail": "ToDoが見つかりません"})
        return self._json(200, {"ok": True})


def run_fallback_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), FallbackTodoHandler)
    print(f"Fallback server running: http://{host}:{port}")
    server.serve_forever()


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    if FastAPI is None:
        run_fallback_server(host=host, port=port)
        return

    try:
        import uvicorn
    except ModuleNotFoundError:
        run_fallback_server(host=host, port=port)
        return

    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
