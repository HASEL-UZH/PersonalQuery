from langchain import hub
from langchain_core.output_parsers import PydanticToolsParser
from langchain_openai import ChatOpenAI

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import ActivityFilterList, State

load_env()
output_parser = PydanticToolsParser(tools=[ActivityFilterList])
prompt_template = hub.pull("activity_selection")


def extract_activities(state: State) -> State:
    if "window_activity" not in state["tables"]:
        return state
    if not state["adjust_query"] and state["branch"] == "follow_up":
        return state

    llm = LLMRegistry.get("openai")
    prompt = prompt_template.invoke(state)

    parsed = llm.with_structured_output(ActivityFilterList).invoke(prompt)

    activities = parsed.list
    state["activities"] = activities
    return state
