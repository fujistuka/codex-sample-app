import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

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

        user = conn.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_USERNAME,)).fetchone()
        if user is None:
            conn.execute(
                "INSERT INTO users(username, password) VALUES (?, ?)",
                (DEFAULT_USERNAME, DEFAULT_PASSWORD),
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


def verify_login(username: str, password: str) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
        return int(row["id"]) if row else None


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
    return row_to_todo(row)


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
    return row_to_todo(row)


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
