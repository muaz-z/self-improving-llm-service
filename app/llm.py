import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.schemas.process_schemas import ProcessResult

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)


async def process_with_prompt(
    message: str,
    prompt: str,
) -> ProcessResult:
    response = await client.responses.parse(
        model="gpt-5-mini",
        input=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        text_format=ProcessResult,
    )

    return response.output_parsed
