from fastapi.testclient import TestClient

from app.main import app
from app.schemas.process_schemas import ProcessResult

client = TestClient(app)


def test_process_success(monkeypatch):
    async def fake_process_with_llm(message: str):
        return (
            1,
            ProcessResult(
                intent="billing",
                sentiment="negative",
                urgency="high",
                entities=["double charge", "refund"],
                needs_human=True,
            ),
        )

    def fake_save_sample(
        message: str,
        output: dict,
        prompt_version: int,
    ):
        return 123

    monkeypatch.setattr(
        "app.apis.process_api.process_with_llm",
        fake_process_with_llm,
    )

    monkeypatch.setattr(
        "app.apis.process_api.save_sample",
        fake_save_sample,
    )

    response = client.post(
        "/process",
        json={"message": "I was charged twice and want a refund."},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sample_id"] == 123
    assert data["prompt_version"] == 1

    assert data["result"] == {
        "intent": "billing",
        "sentiment": "negative",
        "urgency": "high",
        "entities": ["double charge", "refund"],
        "needs_human": True,
    }


def test_process_missing_message():
    response = client.post(
        "/process",
        json={},
    )

    assert response.status_code == 422


def test_process_llm_failure(monkeypatch):
    async def fake_process_with_llm(_: str):
        raise RuntimeError("OpenAI unavailable")

    monkeypatch.setattr(
        "app.apis.process_api.process_with_llm",
        fake_process_with_llm,
    )

    response = client.post(
        "/process",
        json={"message": "I was charged twice."},
    )

    assert response.status_code == 502
