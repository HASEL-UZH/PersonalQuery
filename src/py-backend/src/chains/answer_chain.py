from langchain import hub
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.prompt_values import ChatPromptValue

from helper.answer_utils import convert_bracket_to_dollar_latex
from helper.chat_utils import replace_or_insert_system_prompt
from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import State, AnswerDetail
from langchain_openai import ChatOpenAI

load_env()
prompt_template_partial = hub.pull("partial_answer")
prompt_template_summarize = hub.pull("summarize_answers")

prompt_template = hub.pull("generate_answer")
diagnostic_template = hub.pull("answer-diagnostic")
predictive_template = hub.pull("answer-predictive")
prescriptive_template = hub.pull("answer-prescriptive")
descriptive_template = hub.pull("answer-descriptive")

diagnostic_template_plot = hub.pull("answer-diagnostic-plot")
predictive_template_plot = hub.pull("answer-predictive-plot")
prescriptive_template_plot = hub.pull("answer-prescriptive-plot")
descriptive_template_plot = hub.pull("answer-descriptive-plot")

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


async def generate_answer(state: State, config: dict) -> State:
    """For LangGraph Orchestration"""
    llm = LLMRegistry.get("openai")
    messages = state["messages"]
    insight_mode = state["insight_mode"]
    ws = config.get("configurable", {}).get("websocket")

    code = state['plot_code']
    if code:
        plot = (
                "- The following visualization code was executed to create a plot:\n\n"
                + code
                + "\n\nPlease do not repeat all the details of the data that is used in the plot"
        )
        if insight_mode == "diagnostic":
            template = diagnostic_template_plot
        elif insight_mode == "predictive":
            template = predictive_template_plot
        elif insight_mode == "prescriptive":
            template = prescriptive_template_plot
        else:
            template = descriptive_template_plot
    else:
        plot = ""
        if insight_mode == "diagnostic":
            template = diagnostic_template
        elif insight_mode == "predictive":
            template = predictive_template
        elif insight_mode == "prescriptive":
            template = prescriptive_template
        else:
            template = descriptive_template

    granularity_instruction = {
        AnswerDetail.HIGH: "- Provide a detailed response that remains relevant and focused.",
        AnswerDetail.LOW: "- Provide a concise response that directly answers the user's question. The response should be as high-level as possible. No long bullet point lists of summarizing your findings.",
        AnswerDetail.AUTO: "- Use your judgment to decide the appropriate level of detail based on the question and data."
    }.get(state["answer_detail"], "")

    prompt: ChatPromptValue = template.invoke({
        "question": state["question"],
        "result": state["result"],
        "query": state["query"],
        "plot_code": plot,
        "granularity_instruction": granularity_instruction
    })

    if state['branch'] == "follow_up":
        temp_messages = replace_or_insert_system_prompt(messages, prompt)
        stream = llm.astream(temp_messages)
    else:
        stream = llm.astream(prompt.to_string())
        messages2 = [
            {"role": "system", "content": prompt.messages[0].content}
        ]

    final_msg = AIMessage(content="")

    async for chunk in stream:
        if isinstance(chunk, AIMessageChunk):
            final_msg = chunk if final_msg.content == "" else final_msg + chunk
            if ws:
                await ws.send_json({"type": "chunk", "content": convert_bracket_to_dollar_latex(final_msg.content),
                                    "id": final_msg.id})

    formatted_response = convert_bracket_to_dollar_latex(final_msg.content)
    state["answer"] = formatted_response

    messages.append(AIMessage(
        content=formatted_response,
        id=final_msg.id,
        additional_kwargs={
            "meta": {
                "tables": state["tables"],
                "activities": [a.name for a in state.get("activities") or []],
                "query": state["query"],
                "result": state["raw_result"],
                "plotPath": state.get('plot_path', ""),
                "plotBase64": state.get('plot_base64', ""),
                "fbSubmitted": False
            }
        }
    ))
    return state


async def general_answer(state: State, config: dict) -> State:
    llm = LLMRegistry.get("openai-high-temp")
    prompt = prompt_template_general.invoke(state["current_time"])
    ws = config.get("configurable", {}).get("websocket")

    messages = state["messages"]
    temp_messages = replace_or_insert_system_prompt(messages, prompt)

    stream = llm.astream(temp_messages)
    final_msg = AIMessage(content="")

    async for chunk in stream:
        if isinstance(chunk, AIMessageChunk):
            final_msg = chunk if final_msg.content == "" else final_msg + chunk
            if ws:
                await ws.send_json({"type": "chunk", "content": final_msg.content, "id": final_msg.id})

    state["answer"] = final_msg.content
    assert isinstance(final_msg, AIMessage)
    messages.append(final_msg)
    return state
