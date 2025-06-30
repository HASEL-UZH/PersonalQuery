from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from datetime import date


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
    work_related_typing = Field(
        "work_related_typing",
        description="Estimates how efficiently time was used for typing during work-related tasks, based on keystrokes per second. (Table: user_input, window_activity)"
    )
    input_activity_by_productivity = Field(
        "input_activity_by_productivity",
        description="User input activities linked to productivity (Tables: session, user_input)"
    )
    activity_time_by_productivity = Field(
        "activity_time_by_productivity",
        description="Window activities linked to productivity (Tables: session, window_activity)"
    )
    session_activity_input_summary = Field(
        "session_activity_input_summary",
        description="Summary report, links Window activities and User input activities to productivity (Tables: session, window_activity, user_input)"
    )


class TimeGrouping(str, Enum):
    session = "session"
    day = "day"
    week = "week"
    month = "month"


class SingleDate(BaseModel):
    type: Literal["single"]
    date: date


class DateRange(BaseModel):
    type: Literal["range"]
    from_date: date
    to_date: date


class MultipleDates(BaseModel):
    type: Literal["multiple"]
    dates: List[date]


TimeFilter = Union[SingleDate, DateRange, MultipleDates]


class QueryScope(BaseModel):
    aggregationFeature: Optional[AggregationFeature] = Field(
        default=None,
        description="One behavioral metric to aggregate from high-volume tables like 'window_activity' or 'user_input'."
    )
    timeGrouping: TimeGrouping = Field(
        ..., description="Approximate time scope in order to determine granularity level."
    )
    timeFilter: TimeFilter


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
    original_question: str
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
    aggregation_feature: Optional[AggregationFeature]
    time_grouping: TimeGrouping
    time_filter: TimeFilter
    wants_plot: WantsPlot
    plot_code: str | None
    plot_path: str | None
    plot_base64: str | None
    plot_error: str | None
    plot_attempts: int
    auto_approve: bool
    auto_sql: bool
