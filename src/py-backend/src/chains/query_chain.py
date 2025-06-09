from langchain import hub
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from database import get_db
from helper.env_loader import load_env
from helper.result_utils import format_result_as_markdown, split_result
from llm_registry import LLMRegistry
from schemas import State, QueryOutput

load_env()
db = get_db()

main_template = hub.pull("sql-query-system-prompt")
ui_template = hub.pull("user_input")
wa_template = hub.pull("window_activity")
session_template = hub.pull("session")


def get_custom_table_info(state: State) -> str:
    prompt_parts = []
    tables = state["tables"]
    activities = state.get("activities")

    for table in tables:
        if table == "session":
            prompt_parts.append(session_template.messages[0].prompt.template)

        elif table == "user_input":
            prompt_parts.append(ui_template.messages[0].prompt.template)

        elif table == "window_activity":
            template_input = {
                "activities": (
                    f"-FILTER FOR THESE ACTIVITIES: [{', '.join(activities)}]"
                    if activities else
                    "-DO NOT FILTER ACTIVITIES"
                )
            }
            prompt_value = wa_template.invoke(template_input)
            prompt_parts.append(prompt_value.messages[0].content)

    return "\n\n---\n\n".join(prompt_parts)


def query_chain(llm: ChatOpenAI):
    return (
            RunnableLambda(lambda state: main_template.invoke({
                "dialect": db.dialect,
                "top_k": state.get('top_k', 150),
                "table_info": get_custom_table_info(state) if state["tables"] else db.get_table_info(),
                "input": state["question"]
            }))
            | llm.with_structured_output(QueryOutput)
            | (lambda parsed: parsed["query"])
    )


def write_query(state: State) -> State:
    """For LangGraph Orchestration"""
    llm = LLMRegistry.get("openai")
    query = query_chain(llm).invoke(state)
    state['query'] = query
    return state


def execute_query(state: State) -> State:
    raw_result = db._execute(state["query"])
    state["raw_result"] = raw_result

    chunks = split_result(raw_result)
    state["result"] = [format_result_as_markdown(chunk) for chunk in chunks]
    return state
