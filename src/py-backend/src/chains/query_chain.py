from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from langchain import hub
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from database import get_db
from helper.env_loader import load_env
from helper.result_utils import format_result_as_markdown, split_result
from helper.sql_aggregations import aggregation_sql_templates
from llm_registry import LLMRegistry
from schemas import State, QueryOutput, AdjustQueryDecision, TimeGrouping, Activity, TimeFilter, AggregationFeature

load_env()

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

correct_query_template = hub.pull("correct-query")

aggregation_template_map = {
    item["feature"]: item["sql_template"]
    for item in aggregation_sql_templates
}

browser_activities = {
    Activity.WorkRelatedBrowsing,
    Activity.WorkUnrelatedBrowsing
}
browser_process_list = [
    "Brave Browser",
    "Firefox",
    "Microsoft Edge",
    "Google Chrome",
    "Safari",
    "Opera",
    "Opera GX",
    "Chromium",
    "Vivaldi",
    "Tor Browser",
]


def get_custom_table_info(state: State) -> str:
    prompt_parts = []
    tables = state["tables"]
    activities = state.get("activities", None)
    activities_set = set(activities) if activities else set()

    for table in tables:
        if table == "user_input":
            prompt_parts.append(ui_template.messages[0].prompt.template)
        elif table == "window_activity":
            if activities_set == browser_activities:
                template_input = {
                    "activities": (
                        f"-Filter column `processName` to include only: [{', '.join(browser_process_list)}]"
                    )
                }
            elif activities:
                template_input = {
                    "activities": (
                        f"Filter column `activity` to include only: [{', '.join(a.name for a in activities)}]"
                    )
                }
            else:
                template_input = {
                    "activities": "-DO NOT FILTER ACTIVITIES"
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

    parsed = llm.with_structured_output(AdjustQueryDecision).invoke(prompt)
    state["adjust_query"] = parsed.adjust
    return state


def group_based_on_time_scope(ts: TimeGrouping):
    if ts == ts.session:
        return ""
    if ts == ts.day:
        return "- Use the time grouping: **by hours or sessions **if session table is used as well**.**"
    if ts == ts.week:
        return "- Use the time grouping: **by days**"
    if ts == ts.month:
        return "- Use the time grouping: **by weeks**"


def get_time_filter_prompt(tf: TimeFilter):
    if tf.type == "single":
        return tf.date
    elif tf.type == "range":
        return f"From: {tf.from_date}, To: {tf.to_date}"
    elif tf.type == "multiple":
        return ", ".join(str(d) for d in tf.dates)
    return "No time filter applicable."


def query_chain(llm: ChatOpenAI):
    def select_template(state: State):
        insight_mode = state.get('insight_mode', "descriptive")
        feature: AggregationFeature = state.get("aggregation_feature")

        if feature:
            aggregation_hint = (
                    "- Use the following aggregation SQL template to help write your query:\n\n"
                    + f"-- Feature: {feature.name}\n{aggregation_template_map[feature]}"
                    + "\n\nUse an appropriate column alias for the `{time_bucket}` (e.g., if time grouping is hours, name the column `hour`; if days, name it `day`, etc.)."
            )
        else:
            aggregation_hint = ""

        group_by = group_based_on_time_scope(state.get('time_grouping', TimeGrouping.day))
        time_filter = get_time_filter_prompt(state.get('time_filter'))

        if insight_mode == "diagnostic":
            template = diagnostic_template
        elif insight_mode == "predictive":
            template = predictive_template
        elif insight_mode == "prescriptive":
            template = prescriptive_template
        else:
            template = descriptive_template

        return template.invoke({
            "dialect": "sqlite",
            "top_k": state.get('top_k', 150),
            "table_info": get_custom_table_info(state),
            "question": state["question"],
            "aggregation_hint": aggregation_hint,
            "timeGrouping": group_by,
            "timeFilter": time_filter
        })

    return (
            RunnableLambda(lambda state: select_template(state))
            | llm.with_structured_output(QueryOutput)
            | (lambda parsed: parsed["query"])
    )


def write_query(state: State) -> State:
    """For LangGraph Orchestration"""
    if not state["adjust_query"] and state["branch"] == "follow_up":
        state["query"] = state["last_query"]
        return state
    llm = LLMRegistry.get("openai")
    query = query_chain(llm).invoke(state)
    state['query'] = query
    return state


def execute_query(state: State) -> State:
    def run_query():
        db = get_db()
        raw_result = db._execute(state["query"])
        return raw_result

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_query)
        try:
            # Wait up to 180 seconds
            raw_result = future.result(timeout=180)
            chunks = split_result(raw_result)
            state["raw_result"] = raw_result
            state["result"] = [format_result_as_markdown(chunk) for chunk in chunks]
        except FuturesTimeoutError:
            state["result"] = ["Query execution exceeded 3 minutes and was aborted."]
        except Exception as e:
            state["result"] = [f"Query execution failed: {str(e)}"]
    return state


def correct_query(query, instructions):
    llm = LLMRegistry.get("openai-mini")
    prompt = correct_query_template.invoke({"instruction": instructions,
                                            "query": query})
    parsed = llm.with_structured_output(QueryOutput).invoke(prompt)

    return parsed["query"]


def execute_corrected_query(query):
    def run_query():
        db = get_db()
        return db._execute(query)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_query)
        try:
            # Wait up to 3 minutes (180 seconds)
            result = future.result(timeout=180)
            return result
        except FuturesTimeoutError:
            return {"error": "Query execution exceeded 3 minutes and was aborted."}
        except Exception as e:
            return {"error": f"Query execution failed: {str(e)}"}
