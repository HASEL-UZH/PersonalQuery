from enum import Enum
from typing import List, Literal, Optional, Callable, Awaitable

from pydantic import BaseModel, Field
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import BaseMessage


class QueryOutput(TypedDict):
    """Generated SQL query"""
    query: Annotated[str, ..., "Syntactically valid SQL query."]


class Table(BaseModel):
    """Table in SQL database."""
    name: str = Field(description="Name of table in SQL database.")


class Activity(str, Enum):
    DevCode = Field(
        "DevCode",
        description="Writing or editing source code."
    )
    DevDebug = Field(
        "DevDebug",
        description="Debugging code using tools or logs."
    )
    DevReview = Field(
        "DevReview",
        description="Reviewing code (e.g., pull requests, diffs)."
    )
    DevVc = Field(
        "DevVc",
        description="Using version control tools (e.g., Git clients)."
    )
    Planning = Field(
        "Planning",
        description="Using planning tools like calendars, task managers, project boards."
    )
    ReadWriteDocument = Field(
        "ReadWriteDocument",
        description="Reading or writing documents (e.g., Word, Google Docs)."
    )
    Design = Field(
        "Design",
        description="Graphic, UI, or UX design work."
    )
    GenerativeAI = Field(
        "GenerativeAI",
        description="Using generative AI tools (e.g., ChatGPT, Copilot)."
    )
    PlannedMeeting = Field(
        "PlannedMeeting",
        description="Participating in scheduled meetings."
    )
    Email = Field(
        "Email",
        description="Reading, writing, or organizing emails."
    )
    InstantMessaging = Field(
        "InstantMessaging",
        description="Using chat tools (e.g., Slack, Teams chat)."
    )
    WorkRelatedBrowsing = Field(
        "WorkRelatedBrowsing",
        description="Websites and Browsing that are related to work."
    )
    WorkUnrelatedBrowsing = Field(
        "WorkUnrelatedBrowsing",
        description="Websites and Browsing that are unrelated to work."
    )
    SocialMedia = Field(
        "SocialMedia",
        description="Using platforms like Twitter, Facebook, etc."
    )
    FileManagement = Field(
        "FileManagement",
        description="Managing files or folders (e.g., Explorer, Finder, file transfers)."
    )


class ActivityFilterList(BaseModel):
    """Relevant activity label from activity column in window_activity."""
    list: Optional[List[Activity]] = Field(
        default=None,
        description="One or more Activity(s) to filter the query."
    )




class WantsPlot(str, Enum):
    YES = "YES"
    NO = "NO"
    AUTO = "AUTO"


class AnswerDetail(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"
    AUTO = "AUTO"


class QuestionType(BaseModel):
    questionType: Literal["data_query", "general_qa", "follow_up"] = Field(
        ..., description="Type of question in order to decide what actions to take."
    )
    insightMode: Literal[
        "descriptive", "diagnostic", "predictive", "prescriptive"
    ] = Field(
        ..., description="The analytical intent behind the user's question."
    )


class Question(TypedDict):
    """Type of question asked from the user."""
    question: Annotated[str, ..., "Enriched question by adding time context."]


class AdjustQueryDecision(BaseModel):
    adjust: bool


class AggregationFeature(str, Enum):
    context_switch = Field(
        "context_switch",
        description="Counts how often the user switches between different activity categories, indicating task fragmentation or multitasking. (Table: window_activity)"
    )
    total_focus_time = Field(
        "total_focus_time",
        description="Calculates the total time spent per app and activity, helping identify where most focused attention was directed. (Table: window_activity)"
    )
    category_buckets = Field(
        "category_buckets",
        description="Summarizes total time spent in each activity category (e.g., Work, Planning, Other) to show high-level behavioral distribution. (Table: window_activity)"
    )
    input_activity_volume = Field(
        "input_activity_volume",
        description="Aggregates raw input metrics such as total keystrokes, clicks, mouse movement, and scroll distance to quantify overall interaction volume. (Table: user_input)"
    )
    typing_streaks = Field(
        "typing_streaks",
        description="Counts how many times the user typed continuously, separated by short pauses of more than one minute — a proxy for focus bursts. (Table: user_input)"
    )
    typing_gaps = Field(
        "typing_gaps",
        description="Measures how often long typing breaks (≥5 minutes) occurred, indicating interruptions or disengagement periods. (Table: user_input)"
    )
    user_input_by_app = Field(
        "user_input_by_app",
        description="Breaks down keystrokes, clicks, and mouse activity by app and activity category to show which apps required the most input effort. (Table: user_input, window_activity)"
    )
    typing_density = Field(
        "typing_density",
        description="Calculates average keystrokes per second across the selected period, capturing intensity of typing activity. (Table: user_input)"
    )
    activity_category_ratio = Field(
        "activity_category_ratio",
        description="Computes the proportion of time spent in a specific set of activity categories versus total tracked time, useful for productivity-vs-leisure splits. (Table: window_activity)"
    )
    typing_productivity = Field(
        "typing_productivity",
        description="Estimates how efficiently time was used for productive typing during focus-related activities, based on keystrokes per second. (Table: user_input, window_activity)"
    )


class TimeScope(str, Enum):
    session = "session"
    day = "day"
    week = "week"
    month = "month"


class QueryScope(BaseModel):
    aggregationFeature: Optional[List[AggregationFeature]] = Field(
        default=None,
        description="One or more behavioral metrics to aggregate from high-volume tables like 'window_activity' or 'user_input'."
    )
    timeScope: TimeScope = Field(
        ..., description="Approximate time scope in order to determine granularity level."
    )


class PlotOption(BaseModel):
    wantsPlot: WantsPlot = Field(
        ..., description="Whether the user expects a visual (yes), does not (no)"
    )


class PythonOutput(TypedDict):
    """Generated SQL query"""
    code: Annotated[str, ..., "Syntactically valid python code to create visualizations."]


class State(TypedDict):
    thread_id: str
    messages: List[BaseMessage]
    question: str
    title_exist: bool
    branch: str
    insight_mode: str
    current_time: str
    tables: List[str]
    activities: Optional[List[Activity]]
    query: str
    raw_result: List[dict]
    result: str
    answer: str
    top_k: int
    answer_detail: AnswerDetail
    last_query: str
    adjust_query: bool
    aggregation_feature: Optional[List[AggregationFeature]]
    time_scope: TimeScope
    wants_plot: WantsPlot
    plot_code: str | None
    plot_path: str | None
    plot_base64: str | None
    plot_error: str | None
    plot_attempts: int
    auto_approve: bool
    auto_sql: bool
