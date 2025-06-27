import os
import aiosqlite
from pathlib import Path
from typing import Dict, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import ChatPromptValue

from schemas import WantsPlot, State

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
CHECKPOINT_DB_PATH = APPDATA_PATH / "personal-query" / "chat_checkpoints.db"


async def get_next_thread_id() -> str:
    async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as conn:
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'") as cursor:
            if await cursor.fetchone() is None:
                return "1"

        async with conn.execute("SELECT DISTINCT thread_id FROM checkpoints") as cursor:
            thread_ids = [row[0] async for row in cursor]

    numeric_ids = [int(tid) for tid in thread_ids if tid.isdigit()]
    next_id = max(numeric_ids, default=0) + 1
    return str(next_id)


async def list_chats() -> List[Dict[str, str]]:
    async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as conn:
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'") as cursor:
            if await cursor.fetchone() is None:
                return []

        async with conn.execute("SELECT DISTINCT thread_id FROM checkpoints") as cursor:
            thread_ids = [row[0] async for row in cursor]

        result = []
        for tid in thread_ids:
            async with conn.execute("SELECT title, last_activity FROM chat_metadata WHERE thread_id = ?", (tid,)) as cursor:
                row = await cursor.fetchone()

            title_raw = row[0] if row else None
            title = title_raw.strip() if title_raw and title_raw.strip() else f"New Chat [{tid}]"
            last_activity = row[1] if row and row[1] else None

            result.append({
                "id": tid,
                "title": title,
                "last_activity": last_activity
            })

        return result


async def is_new_chat(thread_id: str) -> bool:
    async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as conn:
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'") as cursor:
            if await cursor.fetchone() is None:
                return True

        async with conn.execute("SELECT 1 FROM checkpoints WHERE thread_id = ? LIMIT 1", (thread_id,)) as cursor:
            result = await cursor.fetchone()

        return result is None


async def title_exists(thread_id: str) -> bool:
    async with aiosqlite.connect(str(CHECKPOINT_DB_PATH)) as conn:
        async with conn.execute("SELECT title FROM chat_metadata WHERE thread_id = ? LIMIT 1", (thread_id,)) as cursor:
            row = await cursor.fetchone()

    return bool(row and row[0] and row[0].strip())


def give_correct_step(current_node: str, state: State) -> str:
    """Predict the next logical step in the workflow based on branch and current node."""
    branch = state.get('branch')
    title_exist = state.get('title_exist')
    wants_plot = state.get('wants_plot')
    auto_sql = state.get('auto_sql')
    auto_approve = state.get('auto_approve')
    if branch == "general_qa":
        return "generate_answer"

    data_query_map = {
        "classify_question": "generate_title" if not title_exist else "give_context",
        "generate_title": "give_context",
        "give_context": "get_tables",
        "get_tables": "extract_activities",
        "extract_activities": "get_scope",
        "get_scope": "write_query",
        "write_query": "execute_query",
        "execute_query": "generate_answer" if wants_plot == WantsPlot.NO else "check_if_plot_needed" if wants_plot == WantsPlot.AUTO else "create_plot",
        "check_if_plot_needed": "generate_answer" if wants_plot == WantsPlot.NO else "create_plot",
        "create_plot": "run_plot_script",
        "run_plot_script": "generate_answer"
    }

    return data_query_map.get(current_node, current_node)


def replace_or_insert_system_prompt(messages: list, prompt: ChatPromptValue) -> list:
    """Replace the first system message or insert one at the beginning if none exists."""
    system_prompt = prompt.messages[0].content
    messages_copy = messages.copy()
    if messages_copy and isinstance(messages_copy[0], SystemMessage):
        messages_copy[0] = SystemMessage(content=system_prompt)
    else:
        messages_copy.insert(0, SystemMessage(content=system_prompt))
    return messages_copy


def replace_or_insert_last_human_msg(messages: list, question: str) -> list:
    """Replace the last HumanMessage in the list with a new one containing the given question.
    If no HumanMessage is found, append the new one to the end.
    """
    messages_copy = messages.copy()
    for i in range(len(messages_copy) - 1, -1, -1):
        if isinstance(messages_copy[i], HumanMessage):
            messages_copy[i] = HumanMessage(content=question)
            return messages_copy
    messages_copy.append(HumanMessage(content=question))
    return messages_copy

