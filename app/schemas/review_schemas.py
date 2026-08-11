from pydantic import BaseModel


class SampleReview(BaseModel):
    sample_id: int
    correct: bool
    feedback: str


class PromptImprovement(BaseModel):
    reason: str
    new_prompt: str


class SampleReviewCollection(BaseModel):
    reviews: list[SampleReview]
