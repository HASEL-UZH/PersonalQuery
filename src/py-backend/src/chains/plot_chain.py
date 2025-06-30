import re
from pathlib import Path
import platform
from langchain import hub

from helper.env_loader import load_env
from llm_registry import LLMRegistry
from schemas import State, PythonOutput, PlotOption

import os
import uuid
import base64
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import matplotlib.font_manager as fm
import plotly.express as px
import plotly.graph_objects as go


load_env()
prompt_template_auto = hub.pull("auto-plot-decision")
prompt_template_create = hub.pull("create-plot-py")
prompt_template_create_again = hub.pull("create-plot-py-again")

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
PLOT_DIR = APPDATA_PATH / "personal-query" / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)


def check_if_plot_needed(state: State):
    llm = LLMRegistry.get("openai")

    prompt = prompt_template_auto.invoke({
        "question": state['question'],
        "result": state['result']
    })

    parsed = llm.with_structured_output(PlotOption).invoke(prompt)
    state["wants_plot"] = parsed.wantsPlot

    return state


def create_plot(state: State):
    llm = LLMRegistry.get("openai")

    result: list[dict] = state['raw_result']

    attempts = state.get("plot_attempts", 0)
    if attempts >= 3:
        state["plot_error"] = "Plot-creation failed after 3 attempts"
        return state
    if attempts == 0:
        prompt = prompt_template_create.invoke({
            "question": state['question'],
            "first_25": state['raw_result'][:25],
            "last_25": state['raw_result'][-25:],
            "num_records": len(result)
        })
    else:
        prompt = prompt_template_create_again.invoke({
            "question": state['question'],
            "first_25": state['raw_result'][:25],
            "last_25": state['raw_result'][-25:],
            "number_of_records": len(result),
            "prev_code": state['plot_code'],
            "prev_error": state['plot_error']
        })

    parsed = llm.with_structured_output(PythonOutput).invoke(prompt)
    state["plot_code"] = parsed["code"]
    state["plot_attempts"] = attempts + 1
    return state


def run_plot_script(state: State) -> State:
    """Execute LLM-generated Python plot code, replace SAVE_PATH, and store result."""
    filename = f"{uuid.uuid4().hex}.png"
    full_path = PLOT_DIR / filename

    code = state.get("plot_code", "")

    if "plt.savefig(SAVE_PATH)" not in code and "fig.write_image(SAVE_PATH)" not in code:
        state["plot_error"] = "SAVE_PATH found, but not used with plt.savefig(...)"
        return state

    code = re.sub(r"SAVE_PATH\s*=\s*['\"].*?['\"]", "", code)
    code = code.replace("SAVE_PATH", f"r'{str(full_path)}'")

    # Strip dummy data and df definitions
    code = re.sub(
        r"(?s)\w+_data\s*=\s*\[.*?\]\s*\n+\w+_df\s*=\s*pd\.DataFrame\s*\(\s*\w+_data\s*\)\s*",
        "", code
    )

    try:
        df = pd.DataFrame(state["raw_result"])
    except Exception as e:
        state["plot_error"] = f"Failed to create DataFrame from raw_result: {e}"
        return state

    try:
        font_path = Path(__file__).resolve().parent.parent.parent / "build" / "DejaVuSans.ttf"
        fm.fontManager.addfont(str(font_path))

        system = platform.system()
        if system == "Windows":
            emoji_font = "Segoe UI Emoji"
        elif system == "Darwin":
            emoji_font = "Apple Color Emoji"
        else:
            emoji_font = "Noto Color Emoji"

        plt.rcParams['font.family'] = ['DejaVu Sans', emoji_font]

        try:
            from qbstyles import mpl_style
            mpl_style(dark=True)
        except Exception as e:
            print("WARNING: Could not apply qbstyles:", e)


    except Exception as e:
        state["plot_error"] = f"Font setup failed: {e}"

    namespace = {
        "plt": plt,
        "px": px,
        "go": go,
        "sns": sns,
        "pd": pd,
        "df": df,
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
