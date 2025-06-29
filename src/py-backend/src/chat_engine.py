import asyncio
import logging
import os
import sqlite3
import uuid

import aiosqlite
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.graph import CompiledGraph

from chains.activity_chain import extract_activities
from chains.answer_chain import generate_answer, general_answer
from chains.plot_chain import check_if_plot_needed, create_plot, run_plot_script
from chains.query_chain import write_query, execute_query, check_query_adjustment
from chains.scope_chain import get_scope
from chains.table_chain import get_tables
from chains.init_chain import classify_question, generate_title
from chains.context_chain import give_context
from helper.chat_utils import title_exists, give_correct_step
from helper.env_loader import load_env
from helper.result_utils import format_result_as_markdown
from schemas import State, WantsPlot, AnswerDetail
from llm_registry import LLMRegistry

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
CHECKPOINT_DB_PATH = APPDATA_PATH / "personal-query" / "chat_checkpoints.db"
DB_PATH = APPDATA_PATH / "personal-query" / "database.sqlite"

graph: CompiledGraph
checkpointer: AsyncSqliteSaver

logging.basicConfig(level=logging.INFO)


async def initialize():
    global graph, checkpointer

    load_env()

    llm_openai = ChatOpenAI(
        model="gpt-4o",
        temperature=0.0,
        base_url="https://api.openai.com/v1",
        api_key=os.getenv("MY_OPENAI_API_KEY")
    )

    llm_openai_high_temp = ChatOpenAI(
        model="gpt-4o",
        temperature=1.0,
        base_url="https://api.openai.com/v1",
        api_key=os.getenv("MY_OPENAI_API_KEY")
    )

    llm_openai_mini = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        base_url="https://api.openai.com/v1",
        api_key=os.getenv("MY_OPENAI_API_KEY")
    )

    llm_llama31 = ChatOpenAI(
        model="llama31instruct",
        temperature=0.0,
        base_url="http://llm.hasel.dev:20769/v1",
        api_key=os.getenv("OPENAI_API_KEY")
    )

    LLMRegistry.register("openai", llm_openai)
    LLMRegistry.register("openai-high-temp", llm_openai_high_temp)
    LLMRegistry.register("openai-mini", llm_openai_mini)
    LLMRegistry.register("llama31", llm_llama31)

    async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as setup_conn:
        await setup_conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_metadata (
                thread_id TEXT PRIMARY KEY,
                title TEXT,
                last_activity TEXT
            )
        """)
        await setup_conn.commit()
        await setup_conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    message_id TEXT,
                    message_content TEXT,
                    data_correct INTEGER,
                    question_answered INTEGER,
                    comment TEXT,
                    created_at TEXT
                )
            """)
        await setup_conn.commit()

    # Then, create a separate connection just for the checkpointer
    saver_conn = await aiosqlite.connect(str(CHECKPOINT_DB_PATH))
    checkpointer = AsyncSqliteSaver(saver_conn)

    graph_builder = StateGraph(State)

    graph_builder.add_node("classify_question", classify_question)
    graph_builder.add_node("generate_title", generate_title)

    graph_builder.add_edge(START, "classify_question")

    graph_builder.add_sequence([
        get_tables,
        extract_activities,
        get_scope,
        write_query,
        execute_query,
    ])

    graph_builder.add_node("general_answer", general_answer)
    graph_builder.add_edge("general_answer", END)

    graph_builder.add_node("check_query_adjustment", check_query_adjustment)
    graph_builder.add_node("give_context", give_context)
    graph_builder.add_node("check_if_plot_needed", check_if_plot_needed)
    graph_builder.add_node("create_plot", create_plot)
    graph_builder.add_node("run_plot_script", run_plot_script)
    graph_builder.add_node("generate_answer", generate_answer)

    graph_builder.add_conditional_edges(
        "give_context",
        lambda s: (
            "get_tables" if s["branch"] == "data_query"
            else "check_query_adjustment"
        ),
        {
            "get_tables": "get_tables",
            "check_query_adjustment": "check_query_adjustment"
        }
    )

    graph_builder.add_conditional_edges(
        "classify_question",
        lambda s: (
            "generate_title" if s["branch"] == "data_query" and not s.get("title_exist", False)
            else "give_context" if s["branch"] != "general_qa"
            else "general_answer"
        ),
        {
            "generate_title": "generate_title",
            "give_context": "give_context",
            "general_answer": "general_answer"
        }
    )

    graph_builder.add_conditional_edges(
        "execute_query",
        lambda s: (
            "create_plot" if s.get("wants_plot") == WantsPlot.YES
            else "check_if_plot_needed" if s.get("wants_plot") == WantsPlot.AUTO
            else "generate_answer"
        ),
        {
            "create_plot": "create_plot",
            "check_if_plot_needed": "check_if_plot_needed",
            "generate_answer": "generate_answer"
        }
    )

    graph_builder.add_conditional_edges(
        "check_if_plot_needed",
        lambda s: (
            "create_plot" if s.get("wants_plot") != WantsPlot.NO
            else "generate_answer"
        ),
        {
            "create_plot": "create_plot",
            "generate_answer": "generate_answer"
        }
    )

    graph_builder.add_edge("create_plot", "run_plot_script")

    graph_builder.add_conditional_edges(
        "run_plot_script",
        lambda s: (
            "create_plot"
            if s.get("plot_error") and s.get("plot_attempts", 0) < 3
            else "generate_answer"
        ),
        {
            "create_plot": "create_plot",
            "generate_answer": "generate_answer"
        }
    )

    graph_builder.add_edge("check_query_adjustment", "get_tables")
    graph_builder.add_edge("generate_title", "give_context")

    graph = graph_builder.compile(checkpointer=checkpointer)


async def run_chat(question: str,
                   chat_id: str,
                   top_k=150, auto_sql=False,
                   auto_approve=False,
                   answer_detail=AnswerDetail.AUTO,
                   wants_plot=WantsPlot.AUTO,
                   websocket=None) -> Dict:
    """Main chat execution."""
    now = datetime.now(UTC).isoformat()
    try:
        async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as conn:
            await conn.execute("""
                    INSERT INTO chat_metadata (thread_id, last_activity)
                    VALUES (?, ?)
                    ON CONFLICT(thread_id) DO UPDATE SET last_activity = excluded.last_activity
                """, (chat_id, now))
            await conn.commit()
    except Exception as e:
        print(f"[update_last_activity] Failed to update chat '{chat_id}': {e}")

    config = {"configurable": {"thread_id": chat_id, "websocket": websocket}}
    current_time = datetime.now().isoformat()

    try:
        snapshot = await graph.aget_state(config)
        messages = snapshot.values.get("messages", [])
    except Exception:
        messages = []

    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages.insert(0, SystemMessage(
            content=(
                "You are a helpful assistant integrated into PersonalQuery — a conversational extension of the "
                "PersonalAnalytics system developed by the Human Aspects of Software Engineering Lab at the University of Zurich.\n\n"
                "PersonalAnalytics is a self-monitoring tool that tracks computer interaction data, including user input, app usage, and website visits. "
                "It also collects self-reported insights through periodic reflection questions, such as perceived productivity. "
                "All data is stored locally to protect user privacy, with optional export and obfuscation tools.\n\n"
                "PersonalQuery enhances this by offering an AI-powered interface for natural, conversational access to the collected data."
                f"\n\nCurrent time: {current_time}"
            )
        ))

    messages.append(HumanMessage(content=question))

    state: State = {
        "thread_id": chat_id,
        "messages": messages,
        "question": question,
        "title_exist": await title_exists(chat_id),
        "branch": "",
        "current_time": current_time,
        "tables": [],
        "activities": [],
        "query": "",
        "raw_result": "",
        "result": [],
        "answer": "",
        "top_k": top_k,
        "last_query": await get_last_query(chat_id),
        "adjust_query": False,
        "wants_plot": wants_plot,
        "answer_detail": answer_detail,
        "auto_sql": auto_sql,
        "auto_approve": auto_approve,
        "plot_code": None,
        "plot_path": None,
        "plot_base64": None,
        "plot_attempts": 0
    }

    if not auto_approve or not auto_sql:
        interrupt_nodes = ["execute_query"]
    else:
        interrupt_nodes = []

    if websocket:
        await websocket.send_json({"type": "step", "node": "classify question"})

    async for step in graph.astream(state, config, stream_mode="updates", interrupt_after=interrupt_nodes):
        node_name = list(step.keys())[0]
        if node_name == "write_query":
            query = step[node_name].get("query")
        if node_name == "execute_query":
            data = step[node_name].get("raw_result")
        if node_name != "__interrupt__":
            step_state = step[node_name]
            branch = step_state.get("branch")
            if websocket:
                next_step = give_correct_step(node_name, step_state)
                await websocket.send_json({"type": "step", "node": next_step})
                await asyncio.sleep(0)

    answer = state['messages'][-1]
    final_msg = {"id": answer.id,
                 "role": "ai",
                 "content": answer.content,
                 "additional_kwargs": answer.additional_kwargs
                 }
    if branch != "general_qa" and (not auto_approve or not auto_sql):
        if websocket:
            await websocket.send_json({
                "type": "interruption",
                "reason": {"auto_sql": auto_sql, "auto_approve": auto_approve},
                "query": query,
                "data": data,
                "chat_id": chat_id
            })
            return {}

    return final_msg


async def resume_stream(chat_id: str, data, websocket) -> Dict:
    config = {"configurable": {"thread_id": chat_id, "websocket": websocket}}
    final_msg = {}
    await graph.aupdate_state(config, {'raw_result': data, 'result': [format_result_as_markdown(data)]})
    state = await graph.aget_state(config)
    if state.values.get("wants_plot") == WantsPlot.AUTO:
        current_step = "check if plot needed"
    elif state.values.get("wants_plot") == WantsPlot.YES:
        current_step = "create plot"
    else:
        current_step = "generate answer"
    await websocket.send_json({"type": "step", "node": current_step})

    try:
        async for step in graph.astream(None, config, stream_mode="updates"):
            node_name = list(step.keys())[0]
            step_state = step[node_name]
            next_step = give_correct_step(node_name, step_state)
            await websocket.send_json({"type": "step", "node": next_step})
            await asyncio.sleep(0)
            if node_name == 'generate_answer':
                answer = step_state.get("messages")[-1]
                final_msg = {
                    "id": answer.id,
                    "role": "ai",
                    "content": answer.content,
                    "additional_kwargs": answer.additional_kwargs
                }
        await websocket.send_json(final_msg)
    except Exception as e:
        logging.error(f"[resume_stream] Failed for chat_id={chat_id}: {e}")
        return {"error": "resume failed"}


async def update_sql_data(chat_id: str, query, data, websocket):
    config = {"configurable": {"thread_id": chat_id, "websocket": websocket}}
    await graph.aupdate_state(config, {'query': query,
                                       'raw_result': data,
                                       'result': [format_result_as_markdown(data)]})
    final_msg = {}
    state = await graph.aget_state(config)
    auto_approve = state.values.get('auto_approve')
    if not auto_approve:
        return
    try:
        async for step in graph.astream(None, config, stream_mode="updates"):
            node_name = list(step.keys())[0]
            step_state = step[node_name]
            await websocket.send_json({"type": "step", "node": node_name})
            await asyncio.sleep(0)
            if node_name == 'generate_answer':
                answer = step_state.get("messages")[-1]
                final_msg = {
                    "id": answer.id,
                    "role": "ai",
                    "content": answer.content,
                    "additional_kwargs": answer.additional_kwargs
                }
        await websocket.send_json(final_msg)
    except Exception as e:
        logging.error(f"[resume_stream] Failed for chat_id={chat_id}: {e}")
        return {"error": "resume failed"}


async def get_chat_history(chat_id: str) -> Dict:
    config = {"configurable": {"thread_id": chat_id}}
    try:
        snapshot = await graph.aget_state(config)
        messages = snapshot.values.get("messages", [])
    except Exception:
        return {"error": "Chat not found"}
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "ai", "content": msg.content, "additional_kwargs": msg.additional_kwargs, "id": msg.id})
        elif isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})

    return {"messages": result}


async def get_last_query(chat_id: str):
    config = {"configurable": {"thread_id": chat_id}}
    try:
        snapshot = await graph.aget_state(config)
        messages = snapshot.values.get("messages", [])
        last_ai_msg = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    except Exception:
        return {"error": "Chat not found"}

    if last_ai_msg is None:
        return None

    meta = last_ai_msg.additional_kwargs.get("meta", {})
    query = meta.get("query")
    return query


async def delete_chat(chat_id: str):
    try:
        async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as conn:
            await conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (chat_id,))
            await conn.execute("DELETE FROM writes WHERE thread_id = ?", (chat_id,))
            await conn.execute("DELETE FROM chat_metadata WHERE thread_id = ?", (chat_id,))
            await conn.commit()

        return {"status": "Chat successfully deleted"}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}


async def rename_chat(chat_id: str, new_title: str):
    try:
        async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as conn:
            await conn.execute("""
                UPDATE chat_metadata
                SET title = ?
                WHERE thread_id = ?
            """, (new_title.strip(), chat_id))
            await conn.commit()

        return {"status": f"Chat title updated to '{new_title.strip()}'"}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}


async def store_feedback(chat_id, msg_id, data_correct, question_answered, comment):
    config: RunnableConfig = {"configurable": {"thread_id": chat_id}}
    try:
        snapshot = await graph.aget_state(config)
        messages = snapshot.values.get("messages", [])
    except Exception:
        return {"error": "Chat not found"}

    targetted_msg = None
    for msg in messages:
        if msg.id == msg_id and isinstance(msg, AIMessage):
            targetted_msg = msg
            break
    if not targetted_msg:
        return {"error": "Message not found."}

    feedback_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    content = targetted_msg.content

    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
    cursor = conn.cursor()

    meta = targetted_msg.additional_kwargs.get("meta", {})
    meta["fbSubmitted"] = True
    targetted_msg.additional_kwargs["meta"] = meta

    await graph.aupdate_state(config, {'messages': messages})

    cursor.execute("""
            INSERT INTO feedback (
                id, thread_id, message_id, message_content,
                data_correct, question_answered, comment, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
        feedback_id,
        chat_id,
        msg_id,
        content,
        data_correct,
        question_answered,
        comment,
        created_at
    ))

    conn.commit()
    conn.close()

    return {"status": "success", "feedback_id": feedback_id}
