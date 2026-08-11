import asyncio

from app.db import ReviewResult
from app.llm import ProcessResult, process_with_prompt
from app.repositories.evaluations import save_prompt_evaluations
from app.reviewer import review_samples

# Cap concurrent candidate reprocessing to avoid provider rate limits
# when the historical regression set grows.
MAX_CONCURRENT_PROCESS_CALLS = 8


async def process_sample_with_limit(
    sample: dict,
    candidate_prompt: str,
    semaphore: asyncio.Semaphore,
) -> ProcessResult:
    async with semaphore:
        return await process_with_prompt(
            message=sample["message"],
            prompt=candidate_prompt,
        )


async def regression_test(
    samples: list[dict],
    baseline_results: dict[int, str],
    candidate_prompt: str,
    candidate_version: int,
) -> bool:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROCESS_CALLS)

    results = await asyncio.gather(
        *[
            process_sample_with_limit(
                sample=sample,
                candidate_prompt=candidate_prompt,
                semaphore=semaphore,
            )
            for sample in samples
        ]
    )

    candidate_samples = [
        {
            "id": sample["id"],
            "message": sample["message"],
            "output_json": result.model_dump_json(),
            "prompt_version": candidate_version,
        }
        for sample, result in zip(samples, results)
    ]

    candidate_reviews = await review_samples(candidate_samples)

    expected_ids = {sample["id"] for sample in samples}
    reviewed_ids = {review.sample_id for review in candidate_reviews}

    if expected_ids != reviewed_ids:
        raise ValueError(
            "Reviewer returned incomplete or unexpected reviews during regression"
        )

    regressions = 0
    improvements = 0
    evaluations = []

    for review in candidate_reviews:
        baseline_result = baseline_results[review.sample_id]

        new_result = (
            ReviewResult.PASSED.value if review.correct else ReviewResult.FAILED.value
        )

        evaluations.append(
            {
                "version": candidate_version,
                "sample_id": review.sample_id,
                "previous_result": baseline_result,
                "current_result": new_result,
                "feedback": review.feedback,
            }
        )

        if (
            baseline_result == ReviewResult.PASSED.value
            and new_result == ReviewResult.FAILED.value
        ):
            regressions += 1

        if (
            baseline_result == ReviewResult.FAILED.value
            and new_result == ReviewResult.PASSED.value
        ):
            improvements += 1

    save_prompt_evaluations(evaluations)

    return regressions == 0 and improvements > 0
