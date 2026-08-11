import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.schemas.process_schemas import ProcessResult
from app.schemas.review_schemas import (
    PromptImprovement,
    SampleReview,
    SampleReviewCollection,
)

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

OUTPUT_SCHEMA_JSON = json.dumps(
    ProcessResult.model_json_schema(),
    indent=2,
)


async def review_samples(
    samples: list[dict],
) -> list[SampleReview]:
    normalized_samples = []

    for sample in samples:
        normalized_samples.append(
            {
                "sample_id": sample["id"],
                "message": sample["message"],
                "output": json.loads(sample["output_json"]),
            }
        )

    response = await client.responses.parse(
        model="gpt-5.4",
        input=[
            {
                "role": "system",
                "content": f"""
                    You are reviewing outputs produced by a smaller customer-support classification model.

                    Judge each sample only against this closed output schema:
                    {OUTPUT_SCHEMA_JSON}

                    For each sample:
                    - determine whether the output is correct given the message and the allowed values above
                    - consider intent, sentiment, urgency, entities, and needs_human
                    - do not invent labels outside the schema
                    - explain any mistake briefly
                    - return one review for every sample
                    """,
            },
            {
                "role": "user",
                "content": json.dumps(normalized_samples),
            },
        ],
        text_format=SampleReviewCollection,
    )

    return response.output_parsed.reviews


async def improve_prompt(
    failed_samples: list[dict],
    current_prompt: str,
) -> PromptImprovement:
    response = await client.responses.parse(
        model="gpt-5.4",
        input=[
            {
                "role": "system",
                "content": f"""
                    You are improving a prompt used by a smaller customer-support classification model.

                    The model must produce outputs that match this closed schema exactly:
                    {OUTPUT_SCHEMA_JSON}

                    Your job is to improve the current prompt based on failed review samples.

                    Requirements:
                    - Preserve the original task.
                    - Preserve the existing output schema and allowed values exactly as defined above.
                    - Fix the weaknesses identified in the failed samples.
                    - Do not overfit to the exact wording of individual samples.
                    - Add general rules that would help with similar future cases.
                    - Return the complete improved prompt, not only the changes.
                    """,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "current_prompt": current_prompt,
                        "failed_samples": failed_samples,
                    }
                ),
            },
        ],
        text_format=PromptImprovement,
    )

    return response.output_parsed
