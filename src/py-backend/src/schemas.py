from typing import List

from pydantic import BaseModel, Field
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import BaseMessage


class State(TypedDict):
    thread_id: str
    messages: List[BaseMessage]
    question: str
    title_exist: bool
    branch: str
    current_time: str
    tables: List[str]
    activities: List[str]
    query: str
    raw_result: str
    result: List[str]
    answer: str
    top_k: int


class QueryOutput(TypedDict):
    """Generated SQL query"""
    query: Annotated[str, ..., "Syntactically valid SQL query."]


class Table(BaseModel):
    """Table in SQL database."""
    name: str = Field(description="Name of table in SQL database.")


class Activity(BaseModel):
    """Relevant activity label from activity column in window_activity."""
    name: str = Field(description="Activity label to use in SQL filtering.")


class QuestionType(TypedDict):
    """Type of question asked from the user."""
    questionType: Annotated[str, ..., "Type of question in order to decide what actions to take."]

class Question(TypedDict):
    """Type of question asked from the user."""
    question: Annotated[str, ..., "Enriched question by adding time context."]
