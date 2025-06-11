from langchain import hub
from langchain_core.output_parsers.openai_tools import PydanticToolsParser
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import Table, State

load_env()
output_parser = PydanticToolsParser(tools=[Table])
prompt_template = hub.pull("get_relevant_tables")


def table_chain(llm: ChatOpenAI) -> RunnableSequence[State, list[str]]:
    return (
            prompt_template
            | llm.bind_tools([Table])
            | output_parser
            | (lambda parsed: [table.name for table in parsed])
    )


def get_tables(state: State) -> State:
    """For LangGraph Orchestration"""
    llm = LLMRegistry.get("openai")
    tables = table_chain(llm).invoke(state)
    state['tables'] = tables
    return state
