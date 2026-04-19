"""Cross-platform smoke test for the ToDo API.

Usage:
  1) Start the app in another terminal:
       python run.py
  2) Run this script:
       python scripts/smoke_test.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def request_json(method: str, path: str, token: str | None = None, payload: dict | None = None) -> dict:
    url = BASE_URL + path
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code} {path}: {body}") from e


def main() -> int:
    try:
        login = request_json("POST", "/api/login", payload={"username": "admin", "password": "password"})
        token = login["token"]
        print("[OK] login")

        todos = request_json("GET", "/api/todos", token=token)
        print(f"[OK] list initial: total={todos['pagination']['total']}")

        created = request_json(
            "POST",
            "/api/todos",
            token=token,
            payload={
                "title": "スモークテスト",
                "priority": 2,
                "due_date": "2026-04-15",
                "tags": ["test", "smoke"],
            },
        )
        todo_id = created["id"]
        print(f"[OK] create: id={todo_id}")

        query = urllib.parse.urlencode(
            {
                "status": "active",
                "sort_by": "priority",
                "order": "asc",
                "page": 1,
                "page_size": 5,
            }
        )
        filtered = request_json("GET", f"/api/todos?{query}", token=token)
        print(f"[OK] filter/sort/page: got={len(filtered['items'])}")

        before_progress = request_json("GET", "/api/progress", token=token)
        print(f"[OK] progress before: xp={before_progress['total_xp']} lv={before_progress['level']}")
        print(f"[OK] login streak: {before_progress['login_streak_days']}日")
        if "all_badges" not in before_progress or "character_state" not in before_progress:
            raise RuntimeError("progress payload missing all_badges or character_state")

        mission = request_json("GET", "/api/daily-mission", token=token)
        print(f"[OK] daily mission loaded: difficulty={mission['difficulty']} candidates={len(mission['candidates'])}")
        mission = request_json("POST", "/api/daily-mission/difficulty", token=token, payload={"difficulty": "easy"})
        main_id = mission["candidates"][0]["id"]
        sub_ids = [mission["candidates"][1]["id"]] if len(mission["candidates"]) > 1 else []
        mission = request_json(
            "POST",
            "/api/daily-mission/select",
            token=token,
            payload={"main_mission_id": main_id, "sub_mission_ids": sub_ids},
        )
        if mission["selected_main_mission_id"] != main_id:
            raise RuntimeError("daily mission selection failed")
        print(f"[OK] daily mission select: main={main_id} sub={len(sub_ids)}")

        review = request_json("GET", "/api/review?days=7", token=token)
        if "metrics" not in review or "character_comment" not in review:
            raise RuntimeError("weekly review payload is incomplete")
        print(f"[OK] weekly review: completed={review['metrics']['completed_tasks']} xp={review['metrics']['gained_xp']}")

        toggled = request_json("PATCH", f"/api/todos/{todo_id}/toggle", token=token)
        print(f"[OK] toggle: completed={toggled['completed']}")
        if "reward" in toggled:
            print(f"[OK] reward: +{toggled['reward']['gained_xp']}xp")

        after_progress = request_json("GET", "/api/progress", token=token)
        if after_progress["total_xp"] <= before_progress["total_xp"]:
            raise RuntimeError("progress xp did not increase after completion")
        if "badge_summary" not in after_progress:
            raise RuntimeError("badge_summary missing in /api/progress")
        print(f"[OK] progress after: xp={after_progress['total_xp']} lv={after_progress['level']}")

        updated = request_json("PUT", f"/api/todos/{todo_id}", token=token, payload={"title": "更新済み"})
        print(f"[OK] update: title={updated['title']}")

        deleted = request_json("DELETE", f"/api/todos/{todo_id}", token=token)
        print(f"[OK] delete: {deleted.get('ok')}")

        print("\nSmoke test completed successfully.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR] {exc}")
        print("サーバーが起動中か確認してください: python run.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
