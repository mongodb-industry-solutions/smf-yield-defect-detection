from typing import Any, List, Literal, Optional
from typing_extensions import TypedDict
from datetime import datetime

# --- Define State Types ---

class TimeseriesRecord(TypedDict):
    timestamp: datetime
    field1: float
    field2: float
    field3: float

class HistoricalRecommendation(TypedDict):
    query: str
    recommendation: str

class AgentState(TypedDict):
    query_reported: str
    chain_of_thought: str
    timeseries_data: List[TimeseriesRecord]
    embedding_vector: List[float]
    historical_recommendations_list: List[HistoricalRecommendation]
    recommendation_text: str
    next_step: Literal[
        "__start__", "start", 
        "reasoning_node", "data_from_csv", "process_data", "embedding_node", 
        "vector_search", "process_vector_search", "persistence_node", "recommendation_node", 
        "__end__", "end"
    ]
    updates: List[str]
    thread_id: Optional[str]