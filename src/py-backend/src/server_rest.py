import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Request
from fastapi.middleware.cors import CORSMiddleware

from chains.query_chain import correct_query, execute_corrected_query
from chat_engine import run_chat, get_chat_history, initialize, delete_chat, rename_chat, resume_stream, \
    update_sql_data, store_feedback
from helper.chat_utils import get_next_thread_id, list_chats
from schemas import AnswerDetail, WantsPlot


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize()
    yield
    logging.info("Backend shutting down")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

active_websocket: Optional[WebSocket] = None


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    global active_websocket
    active_websocket = websocket
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            question = data.get("question", "")
            chat_id = data.get("chat_id", "1")
            top_k = data.get("top_k", 150)
            auto_sql = data.get("auto_sql", True)
            auto_approve = data.get("auto_approve", False)

            answer_detail = {
                'low': AnswerDetail.LOW,
                'high': AnswerDetail.HIGH,
                'auto': AnswerDetail.AUTO
            }.get(data.get("answer_detail", "auto"), AnswerDetail.AUTO)

            wants_plot = {
                'no': WantsPlot.NO,
                'yes': WantsPlot.YES,
                'auto': WantsPlot.AUTO
            }.get(data.get("wants_plot", "auto"), WantsPlot.AUTO)

            msg = await run_chat(question, chat_id, top_k, auto_sql, auto_approve, answer_detail, wants_plot, websocket)
            if msg:
                await websocket.send_json(msg)

    except WebSocketDisconnect:
        active_websocket = None
        logging.info("Client disconnected")


@app.post("/chats")
async def create_chat():
    """Create a new chat and return its thread ID."""
    chat_id = await get_next_thread_id()
    return {"chat_id": chat_id}


@app.get("/chats")
async def get_all_chats():
    """Return a list of all chat thread IDs."""
    return {"chats": await list_chats()}


@app.get("/chats/{chat_id}")
async def get_chat(chat_id: str):
    """Return message history for a given chat."""
    return await get_chat_history(chat_id)


@app.delete("/chats/{chat_id}")
async def remove_chat(chat_id: str):
    return await delete_chat(chat_id)


@app.put("/chats/{chat_id}/rename")
async def rename_chat_endpoint(chat_id: str, new_title: str = Body(..., embed=True)):
    """Rename an existing chat by its chat_id."""
    return await rename_chat(chat_id, new_title)


@app.post("/approval")
async def handle_approval(request: Request):
    payload = await request.json()
    chat_id = payload.get("chat_id")
    approval = payload.get("approval")
    data = payload.get("data")

    if not isinstance(approval, bool):
        return {"status": "error", "message": "Missing or invalid 'approval' boolean."}

    if approval:
        msg = await resume_stream(chat_id, data, active_websocket)
        return msg
    else:
        return {}


@app.post("/correct-query")
async def adjust_query(request: Request):
    payload = await request.json()
    query = payload.get("query")
    instruction = payload.get("instruction")

    query = correct_query(query, instruction)
    return query


@app.post("/execute-query")
async def execute_query(request: Request):
    payload = await request.json()
    query = payload.get("query")

    result = execute_corrected_query(query)
    return result


@app.post("/confirm-query")
async def confirm_query(request: Request):
    payload = await request.json()
    chat_id = payload.get("chat_id")
    query = payload.get("query")
    data = payload.get("data")

    msg = await update_sql_data(chat_id, query, data, active_websocket)
    return msg


@app.post("/feedback")
async def submit_feedback(request: Request):
    payload = await request.json()
    chat_id = payload.get("chat_id")
    msg_id = payload.get("message_id")
    data_correct = payload.get("data_correct")
    question_answered = payload.get("question_answered")
    comment = payload.get("comment")

    status = await store_feedback(chat_id, msg_id, data_correct, question_answered, comment)
    return status


@app.post("/set-env")
async def set_env(request: Request):
    data = await request.json()

    # Only expect OPENAI_API_KEY
    openai_key = data.get("OPENAI_API_KEY", "")
    if not openai_key:
        return {"status": "error", "message": "OPENAI_API_KEY is required"}

    # All environment variables to set
    all_keys = {
        "OPENAI_API_KEY": openai_key,
        "LANGSMITH_TRACING": "false",
        "LANGSMITH_PROJECT": "personalQuery",
        "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
        "LANGSMITH_API_KEY": "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"
    }

    # Update environment in memory
    for key, value in all_keys.items():
        os.environ[key] = value

    # Write .env file
    dotenv_path = os.path.join(os.path.dirname(sys.executable), ".env")
    with open(dotenv_path, "w") as f:
        for key, value in all_keys.items():
            f.write(f"{key}={value}\n")

    return {"status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
