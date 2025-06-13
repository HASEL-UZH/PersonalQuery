from typing import List, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import BaseMessage


class State(TypedDict):
    thread_id: str
    messages: List[BaseMessage]
    question: str
    title_exist: bool
    branch: str
    insight_mode: str
    current_time: str
    tables: List[str]
    activities: List[str]
    query: str
    raw_result: str
    result: List[str]
    answer: str
    top_k: int
    last_query: str
    adjust_query: bool


class QueryOutput(TypedDict):
    """Generated SQL query"""
    query: Annotated[str, ..., "Syntactically valid SQL query."]


class Table(BaseModel):
    """Table in SQL database."""
    name: str = Field(description="Name of table in SQL database.")


class Activity(BaseModel):
    """Relevant activity label from activity column in window_activity."""
    name: str = Field(description="Activity label to use in SQL filtering.")


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
