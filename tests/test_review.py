from fastapi.testclient import TestClient

from app.main import app
from app.schemas.review_schemas import (
    PromptImprovement,
    SampleReview,
)

client = TestClient(app)


def test_review_no_samples(monkeypatch):
    monkeypatch.setattr(
        "app.apis.review_api.get_active_prompt_version",
        lambda: 1,
    )

    monkeypatch.setattr(
        "app.apis.review_api.get_or_create_review_run",
        lambda _: (None, []),
    )

    response = client.post("/review")

    assert response.status_code == 200

    data = response.json()

    assert data["review_run_id"] is None
    assert data["count"] == 0
    assert data["reviews"] == []
    assert data["candidate_prompt_version"] is None
    assert data["regression_passed"] is None
    assert data["activated_candidate"] is False


def test_review_all_samples_pass(monkeypatch):
    samples = [
        {
            "id": 1,
            "message": "I forgot my password.",
            "output_json": """
            {
                "intent": "account_access",
                "sentiment": "neutral",
                "urgency": "medium",
                "entities": ["password"],
                "needs_human": false
            }
            """,
            "prompt_version": 1,
        }
    ]

    async def fake_review_samples(_):
        return [
            SampleReview(
                sample_id=1,
                correct=True,
                feedback="Correct",
            )
        ]

    monkeypatch.setattr(
        "app.apis.review_api.get_active_prompt_version",
        lambda: 1,
    )

    monkeypatch.setattr(
        "app.apis.review_api.get_or_create_review_run",
        lambda _: (10, samples),
    )

    monkeypatch.setattr(
        "app.apis.review_api.review_samples",
        fake_review_samples,
    )

    monkeypatch.setattr(
        "app.apis.review_api.update_sample_reviews",
        lambda _: None,
    )

    monkeypatch.setattr(
        "app.apis.review_api.update_review_run_status",
        lambda **_: None,
    )

    response = client.post("/review")

    assert response.status_code == 200

    data = response.json()

    assert data["review_run_id"] == 10
    assert data["count"] == 1
    assert data["improvement"] is None
    assert data["candidate_prompt_version"] is None
    assert data["regression_passed"] is None
    assert data["activated_candidate"] is False


def test_review_regression_passes_and_activates_candidate(
    monkeypatch,
):
    samples = [
        {
            "id": 1,
            "message": "I forgot my password.",
            "output_json": """
            {
                "intent": "account_access",
                "sentiment": "neutral",
                "urgency": "high",
                "entities": ["password"],
                "needs_human": false
            }
            """,
            "prompt_version": 1,
        }
    ]

    async def fake_review_samples(_):
        return [
            SampleReview(
                sample_id=1,
                correct=False,
                feedback="Urgency should be medium.",
            )
        ]

    async def fake_improve_prompt(
        failed_samples,
        current_prompt,
    ):
        return PromptImprovement(
            reason="Improve password-reset urgency handling",
            new_prompt="Improved prompt",
        )

    async def fake_regression_test(**_):
        return True

    activated_versions = []

    monkeypatch.setattr(
        "app.apis.review_api.get_active_prompt_version",
        lambda: 1,
    )

    monkeypatch.setattr(
        "app.apis.review_api.get_or_create_review_run",
        lambda _: (10, samples),
    )

    monkeypatch.setattr(
        "app.apis.review_api.review_samples",
        fake_review_samples,
    )

    monkeypatch.setattr(
        "app.apis.review_api.update_sample_reviews",
        lambda _: None,
    )

    monkeypatch.setattr(
        "app.apis.review_api.load_prompt",
        lambda _: "Original prompt",
    )

    monkeypatch.setattr(
        "app.apis.review_api.improve_prompt",
        fake_improve_prompt,
    )

    monkeypatch.setattr(
        "app.apis.review_api.get_next_prompt_version",
        lambda: 2,
    )

    monkeypatch.setattr(
        "app.apis.review_api.write_to_prompt_txt",
        lambda **_: None,
    )

    monkeypatch.setattr(
        "app.apis.review_api.save_prompt_version",
        lambda **_: None,
    )

    monkeypatch.setattr(
        "app.apis.review_api.regression_test",
        fake_regression_test,
    )

    monkeypatch.setattr(
        "app.apis.review_api.activate_prompt_version",
        lambda version: activated_versions.append(version),
    )

    monkeypatch.setattr(
        "app.apis.review_api.update_review_run_status",
        lambda **_: None,
    )

    response = client.post("/review")

    assert response.status_code == 200

    data = response.json()

    assert data["candidate_prompt_version"] == 2
    assert data["regression_passed"] is True
    assert data["activated_candidate"] is True

    assert activated_versions == [2]


def test_review_regression_fails_and_does_not_activate(
    monkeypatch,
):
    samples = [
        {
            "id": 1,
            "message": "I forgot my password.",
            "output_json": """
            {
                "intent": "account_access",
                "sentiment": "neutral",
                "urgency": "high",
                "entities": ["password"],
                "needs_human": false
            }
            """,
            "prompt_version": 1,
        }
    ]

    async def fake_review_samples(_):
        return [
            SampleReview(
                sample_id=1,
                correct=False,
                feedback="Urgency should be medium.",
            )
        ]

    async def fake_improve_prompt(
        failed_samples,
        current_prompt,
    ):
        return PromptImprovement(
            reason="Improve urgency classification",
            new_prompt="Candidate prompt",
        )

    async def fake_regression_test(**_):
        return False

    activated_versions = []

    monkeypatch.setattr(
        "app.apis.review_api.get_active_prompt_version",
        lambda: 1,
    )

    monkeypatch.setattr(
        "app.apis.review_api.get_or_create_review_run",
        lambda _: (10, samples),
    )

    monkeypatch.setattr(
        "app.apis.review_api.review_samples",
        fake_review_samples,
    )

    monkeypatch.setattr(
        "app.apis.review_api.update_sample_reviews",
        lambda _: None,
    )

    monkeypatch.setattr(
        "app.apis.review_api.load_prompt",
        lambda _: "Original prompt",
    )

    monkeypatch.setattr(
        "app.apis.review_api.improve_prompt",
        fake_improve_prompt,
    )

    monkeypatch.setattr(
        "app.apis.review_api.get_next_prompt_version",
        lambda: 2,
    )

    monkeypatch.setattr(
        "app.apis.review_api.write_to_prompt_txt",
        lambda **_: None,
    )

    monkeypatch.setattr(
        "app.apis.review_api.save_prompt_version",
        lambda **_: None,
    )

    monkeypatch.setattr(
        "app.apis.review_api.regression_test",
        fake_regression_test,
    )

    monkeypatch.setattr(
        "app.apis.review_api.activate_prompt_version",
        lambda version: activated_versions.append(version),
    )

    monkeypatch.setattr(
        "app.apis.review_api.update_review_run_status",
        lambda **_: None,
    )

    response = client.post("/review")

    assert response.status_code == 200

    data = response.json()

    assert data["candidate_prompt_version"] == 2
    assert data["regression_passed"] is False
    assert data["activated_candidate"] is False

    assert activated_versions == []
