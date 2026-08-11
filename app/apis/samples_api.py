import json
import logging

from fastapi import APIRouter, HTTPException, Query

from app.repositories.samples import list_samples
from app.schemas.sample_schemas import SampleResponse, SamplesResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/samples",
    response_model=SamplesResponse,
)
async def get_samples(
    review_status: str | None = Query(
        default=None,
        description="Filter by review status, e.g. pending or reviewed",
    ),
    prompt_version: int | None = Query(
        default=None,
        description="Filter by prompt version",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of samples to return",
    ),
) -> SamplesResponse:
    try:
        rows = list_samples(
            review_status=review_status,
            prompt_version=prompt_version,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("Failed to list samples")
        raise HTTPException(
            status_code=500,
            detail="Failed to list samples",
        ) from exc

    samples = [
        SampleResponse(
            id=row["id"],
            message=row["message"],
            output=json.loads(row["output_json"]),
            prompt_version=row["prompt_version"],
            review_status=row["review_status"],
            review_result=row["review_result"],
            review_feedback=row["review_feedback"],
            review_run_id=row["review_run_id"],
            reviewed_at=row["reviewed_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return SamplesResponse(
        count=len(samples),
        samples=samples,
    )
