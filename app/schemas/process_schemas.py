from typing import Literal

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    message: str


class ProcessResult(BaseModel):
    intent: Literal[
        "billing",
        "technical",
        "account_access",
        "cancellation",
        "general",
    ]

    sentiment: Literal[
        "positive",
        "neutral",
        "negative",
    ]

    urgency: Literal[
        "low",
        "medium",
        "high",
    ]

    entities: list[str]

    needs_human: bool


class ProcessResponse(BaseModel):
    prompt_version: int
    result: ProcessResult
    sample_id: int
