from fastapi import FastAPI

from app.apis.process_api import router as process_router
from app.apis.prompts_api import router as prompts_router
from app.apis.review_api import router as review_router
from app.apis.samples_api import router as samples_router
from app.db import init_db
from app.logging_config import configure_logging

app = FastAPI(
    title="LearnWise Prompt Improvement Service",
    version="1.0.0",
)

init_db()
configure_logging()


app.include_router(process_router)
app.include_router(review_router)
app.include_router(prompts_router)
app.include_router(samples_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
