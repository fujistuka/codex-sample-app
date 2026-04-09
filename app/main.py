import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ModuleNotFoundError:  # fallback for restricted/offline environments
    FastAPI = None
    HTTPException = Exception
    CORSMiddleware = None
    FileResponse = None
    StaticFiles = None
    BaseModel = object

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

todos: List[Dict[str, object]] = []
next_id = 1


def _add_todo(title: str) -> Dict[str, object]:
    global next_id

    trimmed = title.strip()
    if not trimmed:
        raise ValueError("タイトルは必須です")

    todo = {"id": next_id, "title": trimmed}
    todos.append(todo)
    next_id += 1
    return todo


if FastAPI is not None:
    app = FastAPI(title="Simple ToDo App")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    class TodoCreate(BaseModel):
        title: str

    class Todo(BaseModel):
        id: int
        title: str

    @app.get("/")
    def read_index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/api/todos", response_model=List[Todo])
    def list_todos() -> List[Dict[str, object]]:
        return todos

    @app.post("/api/todos", response_model=Todo)
    def add_todo(todo: TodoCreate) -> Dict[str, object]:
        try:
            return _add_todo(todo.title)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
else:
    app = None


class FallbackTodoHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: Dict[str, object] | List[Dict[str, object]]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _html_file(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            return self._html_file(STATIC_DIR / "index.html")
        if self.path == "/api/todos":
            return self._json(200, todos)
        if self.path.startswith("/static/"):
            file_path = STATIC_DIR / self.path.removeprefix("/static/")
            if file_path.exists() and file_path.is_file():
                content_type = "text/plain; charset=utf-8"
                if file_path.suffix == ".css":
                    content_type = "text/css; charset=utf-8"
                elif file_path.suffix == ".js":
                    content_type = "application/javascript; charset=utf-8"
                elif file_path.suffix == ".html":
                    content_type = "text/html; charset=utf-8"
                return self._text_file(file_path, content_type)
        self._json(404, {"detail": "Not Found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/todos":
            return self._json(404, {"detail": "Not Found"})

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            title = payload.get("title", "")
            todo = _add_todo(title)
            self._json(200, todo)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"detail": "JSONが不正です"})
        except ValueError as error:
            self._json(400, {"detail": str(error)})


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
