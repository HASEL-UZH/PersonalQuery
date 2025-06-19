import re
from pathlib import Path

from langchain import hub

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import State, PythonOutput, PlotOption

import io
import os
import uuid
import base64
import matplotlib.pyplot as plt

load_env()
prompt_template_auto = hub.pull("auto-plot-decision")
prompt_template_create = hub.pull("create-plot-py")
prompt_template_create_again = hub.pull("create-plot-py-again")

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
PLOT_DIR = APPDATA_PATH / "personal-query" / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)


def is_suitable_for_plot(state: State):
    llm = LLMRegistry.get("openai")

    prompt = prompt_template_auto.invoke({
        "question": state['question'],
        "result": state['result']
    })

    parsed = llm.with_structured_output(PlotOption).invoke(prompt)
    state["wants_plot"] = parsed.wantsPlot

    return state


def create_py_plot_code(state: State):
    llm = LLMRegistry.get("openai")

    attempts = state.get("plot_attempts", 0)
    if attempts >= 3:
        state["plot_error"] = "Plot-creation failed after 3 attempts"
        return state
    if attempts == 0:
        prompt = prompt_template_create.invoke({
            "question": state['question'],
            "result": state['result'],
        })
    else:
        prompt = prompt_template_create_again.invoke({
            "question": state['question'],
            "result": state['result'],
            "prev_code": state['plot_code'],
            "prev_error": state['plot_error']
        })

    parsed = llm.with_structured_output(PythonOutput).invoke(prompt)
    state["plot_code"] = parsed["code"]
    state["plot_attempts"] = attempts + 1
    return state


def execute_py_code(state: State) -> State:
    """Execute LLM-generated Python plot code, replace SAVE_PATH, and store result."""
    filename = f"{uuid.uuid4().hex}.png"
    full_path = PLOT_DIR / filename

    code = state.get("plot_code", "")

    if "SAVE_PATH" not in code:
        state["plot_error"] = "LLM code did not contain SAVE_PATH placeholder"
        return state

    if "plt.savefig(SAVE_PATH)" not in code:
        state["plot_error"] = "SAVE_PATH found, but not used with plt.savefig(...)"
        return state

    # Step 1: Remove SAVE_PATH assignment if it exists
    code = re.sub(r"SAVE_PATH\s*=\s*['\"].*?['\"]", "", code)

    # Step 2: Replace all uses of SAVE_PATH with the actual path
    code = code.replace("SAVE_PATH", f"r'{str(full_path)}'")

    namespace = {
        "plt": plt,
        "__builtins__": __builtins__,
    }

    try:
        exec(code, namespace)
        plt.close()

        with open(full_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        state["plot_path"] = str(full_path)
        state["plot_base64"] = f"data:image/png;base64,{b64}"
        state["plot_error"] = None

    except Exception as e:
        state["plot_path"] = ""
        state["plot_base64"] = ""
        state["plot_error"] = str(e)

    return state
