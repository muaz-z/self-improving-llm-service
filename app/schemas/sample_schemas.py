from typing import Any

from pydantic import BaseModel


class SampleResponse(BaseModel):
    id: int
    message: str
    output: dict[str, Any]
    prompt_version: int
    review_status: str
    review_result: str | None
    review_feedback: str | None
    review_run_id: int | None
    reviewed_at: str | None
    created_at: str


class SamplesResponse(BaseModel):
    count: int
    samples: list[SampleResponse]
