from pydantic import BaseModel


class PromptVersionResponse(BaseModel):
    version: int
    reason: str | None
    is_active: bool
    regression_passed: bool | None
    created_at: str
    content: str | None


class PromptsResponse(BaseModel):
    active_version: int | None
    prompts: list[PromptVersionResponse]
