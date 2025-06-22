import logging
import os
import sqlite3
from pathlib import Path

from langchain import hub
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers.openai_tools import PydanticToolsParser
from langchain_core.prompt_values import ChatPromptValue
from langchain_openai import ChatOpenAI

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import QuestionType, State

load_env()
output_parser = PydanticToolsParser(tools=[QuestionType])
prompt_template = hub.pull("classify_question")
prompt_template_title = hub.pull("generate_title")

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
CHECKPOINT_DB_PATH = APPDATA_PATH / "personal-query" / "chat_checkpoints.db"


def classify_chain(llm: ChatOpenAI):
    return (
            prompt_template
            | llm.with_structured_output(QuestionType)
            | (lambda parsed: parsed["questionType"])
    )


def classify_question(state: State) -> State:
    llm = LLMRegistry.get("openai")
    prompt = prompt_template.invoke(state['question'])
    system_prompt = prompt.messages[0].content

    temp_messages = state['messages'].copy()
    if temp_messages and isinstance(temp_messages[0], SystemMessage):
        temp_messages[0] = SystemMessage(content=system_prompt)
    else:
        temp_messages.insert(0, SystemMessage(content=system_prompt))

    parsed = llm.with_structured_output(QuestionType).invoke(temp_messages)
    state['branch'] = parsed.questionType
    state['insight_mode'] = parsed.insightMode
    state['wants_plot'] = parsed.wantsPlot
    return state


def strip_outer_quotes(text: str) -> str:
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1].strip()
    return text.strip()


def generate_title(state: State) -> State:
    """For LangGraph Orchestration"""
    llm = LLMRegistry.get("openai")
    prompt: ChatPromptValue = prompt_template_title.invoke({
        "question": state["question"],
        "max_characters": 25,
        "current_time": state['current_time']
    })

    raw_title = llm.invoke(prompt.to_string()).content
    title = strip_outer_quotes(raw_title)
    thread_id = state["thread_id"]

    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
                UPDATE chat_metadata
                SET title = ?
                WHERE thread_id = ?
            """, (title.strip(), thread_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"[generate_title] Failed to persist title for thread {thread_id}: {e}")

    return state
