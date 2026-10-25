import json
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain.messages import AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field

from app.agent.private_chef import get_agent
from app.config import BASE_DIR, DB_PATH
from app.oss_client import upload_bytes


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(DB_PATH))
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()
    app.state.agent = get_agent(checkpointer=checkpointer)
    app.state.db = conn
    try:
        yield
    finally:
        await conn.close()


app = FastAPI(title="私厨 Agent 服务", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_IMAGE_BYTES = 5 * 1024 * 1024


class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str = "demo"
    image_url: str | None = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="图片超过 5MB，请压缩后再传")
    url = upload_bytes(data, file.filename or "", file.content_type or "image/jpeg")
    return {"url": url, "size": len(data)}


@app.post("/chat")
async def chat(req: ChatIn):
    if req.image_url:
        content = [
            {"type": "text", "text": req.message},
            {"type": "image", "url": req.image_url},
        ]
    else:
        content = req.message

    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        out = await app.state.agent.ainvoke(
            {"messages": [HumanMessage(content=content)]},
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"thread_id": req.thread_id, "reply": out["messages"][-1].content}


@app.post("/chat/stream")
async def chat_stream(req: ChatIn):
    if req.image_url:
        content = [
            {"type": "text", "text": req.message},
            {"type": "image", "url": req.image_url},
        ]
    else:
        content = req.message

    config = {"configurable": {"thread_id": req.thread_id}}

    async def event_stream():
        try:
            async for chunk, meta in app.state.agent.astream(
                {"messages": [HumanMessage(content=content)]},
                config=config,
                stream_mode="messages",
            ):
                if (
                    isinstance(chunk, AIMessageChunk)
                    and meta.get("langgraph_node") == "model"
                    and chunk.content
                ):
                    data = json.dumps(
                        {"type": "delta", "text": chunk.content},
                        ensure_ascii=False,
                    )
                    yield f"data: {data}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as exc:
            data = json.dumps(
                {"type": "error", "message": str(exc)},
                ensure_ascii=False,
            )
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

app.mount("/", StaticFiles(directory=str(BASE_DIR / "web"), html=True), name="web")
