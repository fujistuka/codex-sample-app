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

        toggled = request_json("PATCH", f"/api/todos/{todo_id}/toggle", token=token)
        print(f"[OK] toggle: completed={toggled['completed']}")

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
