from langchain import hub
from langchain_core.output_parsers.openai_tools import PydanticToolsParser
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import State, QueryScope

load_env()
output_parser = PydanticToolsParser(tools=[QueryScope])
prompt_template = hub.pull("get_scope")


def scope_chain(llm: ChatOpenAI) -> RunnableSequence[State, list[str]]:
    return (
            prompt_template
            | llm.bind_tools([QueryScope])
            | output_parser
    )

def get_scope(state: State) -> State:
    llm = LLMRegistry.get("openai")

    prompt = prompt_template.invoke({
        "question": state['question'],
        "tables": state['tables'],
        "current_time": state['current_time']
    })

    parsed = llm.with_structured_output(QueryScope).invoke(prompt)
    state["aggregation_feature"] = parsed.aggregationFeature
    state["time_grouping"] = parsed.timeGrouping
    state["time_filter"] = parsed.timeFilter
    return state
