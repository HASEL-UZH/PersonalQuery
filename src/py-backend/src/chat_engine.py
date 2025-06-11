import asyncio
import logging
import os
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.graph import CompiledGraph

from chains.activity_chain import extract_activities
from chains.answer_chain import generate_answer, general_answer
from chains.query_chain import write_query, execute_query
from chains.table_chain import get_tables
from chains.init_chain import classify_question, generate_title
from chains.context_chain import give_context
from helper.chat_utils import title_exists, give_correct_step
from helper.db_modification import update_sessions_from_usage_data, add_window_activity_durations
from helper.env_loader import load_env
from helper.result_utils import format_result_as_markdown
from schemas import State
from llm_registry import LLMRegistry

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
CHECKPOINT_DB_PATH = APPDATA_PATH / "personal-query" / "chat_checkpoints.db"
DB_PATH = APPDATA_PATH / "personal-query" / "database.sqlite"

graph: CompiledGraph
checkpointer: SqliteSaver

logging.basicConfig(level=logging.INFO)  # Ensure logging works even if not set up yet
logging.info(f"👀 chat_engine.py loaded in PID: {os.getpid()}")


def initialize():
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

    graph_builder = StateGraph(State)

    graph_builder.add_node("classify_question", classify_question)
    graph_builder.add_node("generate_title", generate_title)

    graph_builder.add_edge(START, "classify_question")

    graph_builder.add_sequence([
        give_context,
        get_tables,
        extract_activities,
        write_query,
        execute_query,
        generate_answer
    ])

    graph_builder.add_node("general_answer", general_answer)
    graph_builder.add_edge("general_answer", END)

    graph_builder.add_conditional_edges(
        "classify_question",
        lambda s: (
            "generate_title" if s["branch"] == "data_query" and not s.get("title_exist", False)
            else "give_context" if s["branch"] == "data_query"
            else "general_answer"
        ),
        {
            "generate_title": "generate_title",
            "give_context": "give_context",
            "general_answer": "general_answer"
        }
    )

    graph_builder.add_edge("generate_title", "give_context")

    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = graph_builder.compile(checkpointer=checkpointer)

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_metadata (
            thread_id TEXT PRIMARY KEY,
            title TEXT,
            last_activity TEXT
        )
    """)


async def run_chat(question: str, chat_id: str, top_k=150, auto_approve=False, on_update=None) -> Dict:
    """Main chat execution."""
    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
                INSERT INTO chat_metadata (thread_id, last_activity)
                VALUES (?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET last_activity = excluded.last_activity
            """, (chat_id, now))
    conn.commit()
    conn.close()

    config = {"configurable": {"thread_id": chat_id}}
    current_time = datetime.now().isoformat()

    try:
        snapshot = graph.get_state(config)
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
        "title_exist": title_exists(chat_id),
        "branch": "",
        "current_time": current_time,
        "tables": [],
        "activities": [],
        "query": "",
        "raw_result": "",
        "result": [],
        "answer": "",
        "top_k": top_k
    }

    interrupt_nodes = [] if auto_approve else ["generate_answer"]

    if on_update:
        await on_update({"type": "step", "node": "classify question"})

    for step in graph.stream(state, config, stream_mode="updates", interrupt_before=interrupt_nodes):
        node_name = list(step.keys())[0]
        if node_name == "execute_query":
            data = step[node_name].get("raw_result")
        if node_name != "__interrupt__":
            step_state = step[node_name]
            branch = step_state.get("branch")
            if on_update:
                next_step = give_correct_step(node_name, branch, step_state.get('title_exist'))
                await on_update({"type": "step", "node": next_step})
                await asyncio.sleep(0)

    answer = state['messages'][-1]
    final_msg = {"role": "ai", "content": answer.content, "additional_kwargs": answer.additional_kwargs}

    if branch == 'data_query' and not auto_approve:
        if on_update:
            await on_update({
                "type": "approval",
                "data": data,
                "chat_id": chat_id
            })
            return {}

    return final_msg


def resume_stream(chat_id: str, data) -> Dict:
    config = {"configurable": {"thread_id": chat_id}}
    final_msg = {}
    graph.update_state(config, {'raw_result': data, 'result': [format_result_as_markdown(data)]})

    try:
        for step in graph.stream(None, config, stream_mode="updates"):
            node_name = list(step.keys())[0]
            step_state = step[node_name]
            answer = step_state.get("messages")[-1]
            final_msg = {
                "role": "ai",
                "content": answer.content,
                "additional_kwargs": answer.additional_kwargs
            }
        return final_msg
    except Exception as e:
        logging.error(f"[resume_stream] Failed for chat_id={chat_id}: {e}")
        return {"error": "resume failed"}


def get_chat_history(chat_id: str) -> Dict:
    config = {"configurable": {"thread_id": chat_id}}

    try:
        snapshot = graph.get_state(config)
        messages = snapshot.values.get("messages", [])
    except Exception:
        return {"error": "Chat not found"}
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "ai", "content": msg.content, "additional_kwargs": msg.additional_kwargs})
        elif isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})

    return {"messages": result}


def delete_chat(chat_id: str):
    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (chat_id,))
        cursor.execute("DELETE FROM writes WHERE thread_id = ?", (chat_id,))

        cursor.execute("DELETE FROM chat_metadata WHERE thread_id = ?", (chat_id,))

        conn.commit()
        conn.close()

        return {"status": "Chat successfully deleted"}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}


def rename_chat(chat_id: str, new_title: str):
    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE chat_metadata
            SET title = ?
            WHERE thread_id = ?
        """, (new_title.strip(), chat_id))

        conn.commit()
        conn.close()

        return {"status": f"Chat title updated to '{new_title.strip()}'"}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}
