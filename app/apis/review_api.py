import json
import logging

from fastapi import APIRouter, HTTPException

from app.db import ReviewResult, ReviewRunStatus
from app.prompts import (
    delete_prompt_txt,
    get_next_prompt_version,
    load_prompt,
    write_to_prompt_txt,
)
from app.regression import regression_test
from app.repositories.prompts import (
    activate_prompt_version,
    get_active_prompt_version,
    save_prompt_version,
    update_prompt_regression,
)
from app.repositories.review_runs import (
    create_review_run,
    get_resumable_review_run,
    update_review_run_status,
)
from app.repositories.samples import (
    assign_samples_to_review_run,
    get_pending_samples,
    get_samples_for_review_run,
    get_successful_samples,
    update_sample_reviews,
)
from app.reviewer import improve_prompt, review_samples
from app.schemas.review_schemas import SampleReview

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/review")
async def review():
    try:
        active_prompt_version = get_active_prompt_version()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to load active prompt version",
        ) from exc
    logger.info(
        "Starting review for prompt version %s",
        active_prompt_version,
    )

    improvement = None
    candidate_version = None
    regression_passed = None
    activated_candidate = False

    review_run_id, samples = get_or_create_review_run(active_prompt_version)

    if not samples:
        return {
            "review_run_id": review_run_id,
            "count": 0,
            "reviews": [],
            "improvement": improvement,
            "candidate_prompt_version": candidate_version,
            "regression_passed": regression_passed,
            "reviewed_prompt_version": active_prompt_version,
            "activated_candidate": activated_candidate,
        }

    logger.info(
        "Review run %s processing %s samples",
        review_run_id,
        len(samples),
    )

    #
    # Everything below belongs to this review run.
    # Any failure marks the run as FAILED.
    #
    try:
        #
        # Review current outputs
        #
        try:
            reviews = await review_samples(samples)
        except Exception as exc:
            logger.exception(
                "Reviewer LLM failed for review run %s",
                review_run_id,
            )

            raise HTTPException(
                status_code=502,
                detail="Reviewer LLM failed",
            ) from exc

        # Ensure the reviewer returned exactly one result
        # for every sample we sent. no more, no less.
        expected_ids = {sample["id"] for sample in samples}

        reviewed_ids = {review.sample_id for review in reviews}

        if expected_ids != reviewed_ids:
            raise HTTPException(
                status_code=502,
                detail="Reviewer returned incomplete or unexpected reviews",
            )

        #
        # Persist sample review results
        #
        try:
            update_sample_reviews(reviews)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="Failed to update sample reviews",
            ) from exc

        #
        # Build failed samples
        #
        sample_map = {sample["id"]: sample for sample in samples}

        failed_sample_reviews = [review for review in reviews if not review.correct]

        failed_samples = [
            {
                "sample_id": review.sample_id,
                "message": sample_map[review.sample_id]["message"],
                "output": json.loads(sample_map[review.sample_id]["output_json"]),
                "feedback": review.feedback,
            }
            for review in failed_sample_reviews
        ]

        logger.info(
            "Review run %s: %s failed samples",
            review_run_id,
            len(failed_samples),
        )

        #
        # Only generate a candidate if something failed.
        #
        if failed_samples:
            (
                improvement,
                candidate_version,
                regression_passed,
                activated_candidate,
            ) = await run_prompt_improvement(
                active_prompt_version=active_prompt_version,
                samples=samples,
                reviews=reviews,
                failed_samples=failed_samples,
            )

        # A review run is completed if the workflow itself
        # finished successfully, even when:
        #
        # - there were no failed samples
        # - regression returned False
        #
        try:
            update_review_run_status(
                review_run_id=review_run_id,
                status=ReviewRunStatus.COMPLETED.value,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="Failed to complete review run",
            ) from exc

    except HTTPException:
        mark_review_run_failed(review_run_id)
        raise

    except Exception as exc:
        mark_review_run_failed(review_run_id)

        raise HTTPException(
            status_code=500,
            detail="Review run failed",
        ) from exc

    return {
        "review_run_id": review_run_id,
        "count": len(reviews),
        "reviews": reviews,
        "improvement": improvement,
        "candidate_prompt_version": candidate_version,
        "regression_passed": regression_passed,
        "reviewed_prompt_version": active_prompt_version,
        "activated_candidate": activated_candidate,
    }


def get_or_create_review_run(prompt_version: int) -> tuple[int | None, list[dict]]:
    try:
        #
        # Resume an existing failed/running review run
        #
        resumable_run = get_resumable_review_run(
            prompt_version=prompt_version,
        )

        if resumable_run:
            review_run_id = resumable_run["id"]

            samples = get_samples_for_review_run(
                review_run_id=review_run_id,
            )

            update_review_run_status(
                review_run_id=review_run_id,
                status=ReviewRunStatus.RUNNING.value,
            )

            return review_run_id, samples

        #
        # Otherwise create a new review run
        #
        samples = get_pending_samples(
            prompt_version=prompt_version,
        )

        if not samples:
            return None, []

        review_run_id = create_review_run(
            prompt_version=prompt_version,
        )

        assign_samples_to_review_run(
            sample_ids=[sample["id"] for sample in samples],
            review_run_id=review_run_id,
        )

        return review_run_id, samples

    except Exception as exc:
        logger.exception(
            "Failed to get or create review run for prompt version %s",
            prompt_version,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to get or create review run",
        ) from exc


def mark_review_run_failed(review_run_id: int) -> None:
    try:
        update_review_run_status(
            review_run_id=review_run_id,
            status=ReviewRunStatus.FAILED.value,
        )
    except Exception:
        logger.exception("Failed to mark review_run_id=%s as FAILED", review_run_id)


async def run_prompt_improvement(
    *,
    active_prompt_version: int,
    samples: list[dict],
    reviews: list[SampleReview],
    failed_samples: list[dict],
):
    try:
        current_prompt = load_prompt(active_prompt_version)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to load current prompt",
        ) from exc

    try:
        improvement = await improve_prompt(
            failed_samples=failed_samples,
            current_prompt=current_prompt,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate improved prompt",
        ) from exc

    #
    # Persist candidate prompt version.
    #
    try:
        candidate_version = get_next_prompt_version()

        write_to_prompt_txt(
            version=candidate_version,
            content=improvement.new_prompt,
        )

        try:
            save_prompt_version(
                version=candidate_version,
                reason=improvement.reason,
                is_active=False,
            )
        except Exception:
            delete_prompt_txt(candidate_version)
            raise

        logger.info(
            "Created candidate prompt v%s from prompt v%s",
            candidate_version,
            active_prompt_version,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to persist candidate prompt",
        ) from exc

    try:
        regression_samples, baseline_results = build_regression_set(
            samples=samples,
            reviews=reviews,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to build regression set",
        ) from exc

    try:
        regression_passed = await regression_test(
            samples=regression_samples,
            baseline_results=baseline_results,
            candidate_prompt=improvement.new_prompt,
            candidate_version=candidate_version,
        )
    except Exception as exc:
        logger.exception(
            "Regression testing failed for candidate v%s",
            candidate_version,
        )

        raise HTTPException(
            status_code=500,
            detail="Regression testing failed",
        ) from exc

    try:
        update_prompt_regression(
            version=candidate_version,
            regression_passed=regression_passed,
        )
    except Exception as exc:
        logger.exception(
            "Failed to persist regression result for candidate v%s",
            candidate_version,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to persist regression result",
        ) from exc

    logger.info(
        "Candidate v%s regression_passed=%s",
        candidate_version,
        regression_passed,
    )

    activated_candidate = False

    if regression_passed:
        try:
            activate_prompt_version(candidate_version)
            activated_candidate = True

            logger.info(
                "Promoted candidate prompt v%s",
                candidate_version,
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="Failed to activate candidate prompt",
            ) from exc

    return (
        improvement,
        candidate_version,
        regression_passed,
        activated_candidate,
    )


def build_regression_set(
    *,
    samples: list[dict],
    reviews: list[SampleReview],
) -> tuple[list[dict], dict[int, str]]:

    successful_samples = get_successful_samples()

    baseline_results = {
        sample["id"]: ReviewResult.PASSED.value for sample in successful_samples
    }

    baseline_results.update(
        {
            review.sample_id: (
                ReviewResult.PASSED.value
                if review.correct
                else ReviewResult.FAILED.value
            )
            for review in reviews
        }
    )

    regression_sample_map = {sample["id"]: sample for sample in successful_samples}

    regression_sample_map.update({sample["id"]: sample for sample in samples})

    regression_samples = list(regression_sample_map.values())

    return regression_samples, baseline_results
