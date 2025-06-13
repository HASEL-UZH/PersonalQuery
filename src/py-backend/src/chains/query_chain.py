from langchain import hub
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from database import get_db
from helper.chat_utils import replace_or_insert_system_prompt
from helper.env_loader import load_env
from helper.result_utils import format_result_as_markdown, split_result
from llm_registry import LLMRegistry
from schemas import State, QueryOutput, AdjustQueryDecision

load_env()
db = get_db()

main_template = hub.pull("sql-query-system-prompt")

diagnostic_template = hub.pull("diagnostic-sql-query")
predictive_template = hub.pull("predictive-sql-query")
prescriptive_template = hub.pull("prescriptive-sql-query")
descriptive_template = hub.pull("descriptive-sql-query")

ui_template = hub.pull("user_input")
wa_template = hub.pull("window_activity")
session_template = hub.pull("session")

adjust_query_decision_template = hub.pull("adjust-query-decision")
adjust_query_template = hub.pull("adjust-query")


def get_custom_table_info(state: State) -> str:
    prompt_parts = []
    tables = state["tables"]
    activities = state.get("activities")

    for table in tables:
        if table == "user_input":
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
        elif table == "session":
            prompt_parts.append(session_template.messages[0].prompt.template)

    return "\n\n---\n\n".join(prompt_parts)


def check_query_adjustment(state: State) -> State:
    llm = LLMRegistry.get("openai")

    prompt = adjust_query_decision_template.invoke({
        "question": state["question"],
        "last_query": state["last_query"]
    })

    messages = state["messages"].copy()
    temp_messages = replace_or_insert_system_prompt(messages, prompt)

    parsed = llm.with_structured_output(AdjustQueryDecision).invoke(temp_messages)
    state["adjust_query"] = parsed.adjust
    return state


def query_chain(llm: ChatOpenAI):
    def select_template(state: State):
        insight_mode = state.get('insight_mode', "descriptive")
        update = state.get('adjust_query', False)
        if update:
            return adjust_query_template.invoke({
                "dialect": db.dialect,
                "top_k": state.get('top_k', 150),
                "table_info": get_custom_table_info(state) if state["tables"] else db.get_table_info(),
                "question": state["question"],
                "last_query": state["last_query"]
            })
        if insight_mode == "diagnostic":
            template = diagnostic_template
        elif insight_mode == "predictive":
            template = predictive_template
        elif insight_mode == "prescriptive":
            template = prescriptive_template
        else:
            template = descriptive_template

        return template.invoke({
            "dialect": db.dialect,
            "top_k": state.get('top_k', 150),
            "table_info": get_custom_table_info(state) if state["tables"] else db.get_table_info(),
            "question": state["question"]
        })

    return (
        RunnableLambda(lambda state: select_template(state))
        | llm.with_structured_output(QueryOutput)
        | (lambda parsed: parsed["query"])
    )


def write_query(state: State) -> State:
    """For LangGraph Orchestration"""
    if not state["adjust_query"] and state["branch"] == "follow_up":
        return state
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
