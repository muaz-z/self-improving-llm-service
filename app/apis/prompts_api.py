import logging

from fastapi import APIRouter, HTTPException

from app.prompts import load_prompt
from app.repositories.prompts import list_prompt_versions
from app.schemas.prompt_schemas import PromptsResponse, PromptVersionResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/prompts",
    response_model=PromptsResponse,
)
async def get_prompts() -> PromptsResponse:
    try:
        versions = list_prompt_versions()
    except Exception as exc:
        logger.exception("Failed to list prompt versions")
        raise HTTPException(
            status_code=500,
            detail="Failed to list prompt versions",
        ) from exc

    prompts = []
    active_version = None

    for version in versions:
        if version["is_active"]:
            active_version = version["version"]

        try:
            content = load_prompt(version["version"])
        except FileNotFoundError:
            logger.warning(
                "Prompt file missing for version %s",
                version["version"],
            )
            content = None

        prompts.append(
            PromptVersionResponse(
                version=version["version"],
                reason=version["reason"],
                is_active=version["is_active"],
                regression_passed=version["regression_passed"],
                created_at=version["created_at"],
                content=content,
            )
        )

    return PromptsResponse(
        active_version=active_version,
        prompts=prompts,
    )
