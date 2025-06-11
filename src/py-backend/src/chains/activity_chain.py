from langchain import hub
from langchain_core.output_parsers import PydanticToolsParser
from langchain_openai import ChatOpenAI

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import Activity, State

load_env()
output_parser = PydanticToolsParser(tools=[Activity])
prompt_template = hub.pull("activity_selection")


def activity_chain(llm: ChatOpenAI):
    return (
            prompt_template
            | llm.bind_tools([Activity])
            | output_parser
            | (lambda acts: [a.name for a in acts])
    )


def extract_activities(state: State) -> State:
    if "window_activity" not in state["tables"]:
        return state

    llm = LLMRegistry.get("openai")
    activities = activity_chain(llm).invoke(state)
    state["activities"] = activities
    return state
