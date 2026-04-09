from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


app = FastAPI(title="Simple ToDo App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


class TodoCreate(BaseModel):
    title: str


class Todo(BaseModel):
    id: int
    title: str


todos: List[Todo] = []
next_id = 1


@app.get("/")
def read_index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/api/todos", response_model=List[Todo])
def list_todos() -> List[Todo]:
    return todos


@app.post("/api/todos", response_model=Todo)
def add_todo(todo: TodoCreate) -> Todo:
    global next_id

    title = todo.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="タイトルは必須です")

    new_todo = Todo(id=next_id, title=title)
    todos.append(new_todo)
    next_id += 1
    return new_todo
