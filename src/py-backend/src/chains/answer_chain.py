from langchain import hub
from langchain_core.messages import AIMessage
from langchain_core.prompt_values import ChatPromptValue

from helper.answer_utils import convert_bracket_to_dollar_latex
from helper.chat_utils import replace_or_insert_system_prompt
from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import State
from langchain_openai import ChatOpenAI

load_env()
prompt_template_partial = hub.pull("partial_answer")
prompt_template_summarize = hub.pull("summarize_answers")

prompt_template = hub.pull("generate_answer")
diagnostic_template = hub.pull("answer-diagnostic")
predictive_template = hub.pull("answer-predictive")
prescriptive_template = hub.pull("answer-prescriptive")
descriptive_template = hub.pull("answer-descriptive")

prompt_template_general = hub.pull("general_answer")


def answer_chain(llm: ChatOpenAI, state: State):
    """Answer question using retrieved information as context."""
    prompt = (
        "Given the following user question, corresponding SQL query, "
        "and SQL result, answer the user question.\n\n"
        f'Question: {state["question"]}\n'
        f'SQL Query: {state["query"]}\n'
        f'SQL Result: {state["result"]}'
    )
    response = llm.invoke(prompt)
    return response.content


def generate_answer(state: State) -> State:
    """For LangGraph Orchestration"""
    llm = LLMRegistry.get("openai")
    messages = state["messages"]
    insight_mode = state["insight_mode"]

    if insight_mode == "diagnostic":
        template = diagnostic_template
    elif insight_mode == "predictive":
        template = predictive_template
    elif insight_mode == "prescriptive":
        template = prescriptive_template
    else:
        template = descriptive_template

    prompt: ChatPromptValue = template.invoke({
        "question": state["question"],
        "result": state["result"],
        "current_time": state["current_time"]
    })
    if state['branch'] == "follow_up":
        temp_messages = replace_or_insert_system_prompt(messages, prompt)
        response = llm.invoke(temp_messages).content
    else:
        response = llm.invoke(prompt.to_string()).content

    formatted_response = convert_bracket_to_dollar_latex(response)

    state["answer"] = formatted_response

    messages.append(AIMessage(
        content=formatted_response,
        additional_kwargs={
            "meta": {
                "tables": state["tables"],
                "activities": state["activities"],
                "query": state["query"],
                "result": state["raw_result"]
            }
        }
    ))
    return state


def general_answer(state: State) -> State:
    prompt = prompt_template_general.invoke(state['current_time'])

    llm = LLMRegistry.get("openai-high-temp")
    messages = state["messages"]
    temp_messages = replace_or_insert_system_prompt(messages, prompt)

    response = llm.invoke(temp_messages).content
    state["answer"] = response
    messages.append(AIMessage(content=response))
    return state
