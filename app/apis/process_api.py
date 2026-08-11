import logging

from fastapi import APIRouter, HTTPException

from app.llm import ProcessResult, process_with_prompt
from app.prompts import load_prompt
from app.repositories.prompts import get_active_prompt_version
from app.repositories.samples import save_sample
from app.schemas.process_schemas import ProcessRequest, ProcessResponse

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post(
    "/process",
    response_model=ProcessResponse,
)
async def process(
    request: ProcessRequest,
) -> ProcessResponse:
    logger.info("Processing request")

    try:
        prompt_version, result = await process_with_llm(request.message)
    except Exception as exc:
        logger.exception("Processing failed")

        raise HTTPException(
            status_code=502,
            detail="Failed to process message with LLM",
        ) from exc

    logger.info(
        "Using prompt version %s",
        prompt_version,
    )

    try:
        sample_id = save_sample(
            message=request.message,
            output=result.model_dump(),
            prompt_version=prompt_version,
        )

        logger.info(
            "Persisted sample %s",
            sample_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to persist processed sample",
        ) from exc

    return ProcessResponse(
        prompt_version=prompt_version,
        result=result,
        sample_id=sample_id,
    )


async def process_with_llm(
    message: str,
) -> tuple[int, ProcessResult]:
    prompt_version = get_active_prompt_version()
    prompt = load_prompt(prompt_version)

    result = await process_with_prompt(
        message=message,
        prompt=prompt,
    )

    return prompt_version, result
