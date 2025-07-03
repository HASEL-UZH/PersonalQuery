from langchain import hub
from langchain_core.messages import SystemMessage

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import State, Question

load_env()
prompt_template = hub.pull("give_context")


def give_context(state: State) -> State:
    prompt = prompt_template.invoke(state['current_time'])
    system_prompt = prompt.messages[0].content

    llm = LLMRegistry.get("openai")
    messages = state['messages']
    temp_messages = messages.copy()

    if temp_messages and isinstance(temp_messages[0], SystemMessage):
        temp_messages[0] = SystemMessage(content=system_prompt)
    else:
        temp_messages.insert(0, SystemMessage(content=system_prompt))

    enriched_question = llm.with_structured_output(Question).invoke(temp_messages)
    state['question'] = enriched_question

    return state
