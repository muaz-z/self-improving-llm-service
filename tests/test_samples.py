from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_samples(monkeypatch):
    monkeypatch.setattr(
        "app.apis.samples_api.list_samples",
        lambda **_: [
            {
                "id": 2,
                "message": "I want a refund.",
                "output_json": """
                {
                    "intent": "billing",
                    "sentiment": "negative",
                    "urgency": "high",
                    "entities": ["refund"],
                    "needs_human": true
                }
                """,
                "prompt_version": 1,
                "review_status": "reviewed",
                "review_result": "passed",
                "review_feedback": "Correct",
                "review_run_id": 10,
                "reviewed_at": "2026-01-02T00:00:00+00:00",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )

    response = client.get("/samples")

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert data["samples"][0]["id"] == 2
    assert data["samples"][0]["review_status"] == "reviewed"
    assert data["samples"][0]["review_result"] == "passed"
    assert data["samples"][0]["output"]["intent"] == "billing"


def test_get_samples_passes_filters(monkeypatch):
    captured = {}

    def fake_list_samples(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "app.apis.samples_api.list_samples",
        fake_list_samples,
    )

    response = client.get(
        "/samples",
        params={
            "review_status": "pending",
            "prompt_version": 3,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "review_status": "pending",
        "prompt_version": 3,
        "limit": 10,
    }
