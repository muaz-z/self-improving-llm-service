from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_prompts(monkeypatch):
    monkeypatch.setattr(
        "app.apis.prompts_api.list_prompt_versions",
        lambda: [
            {
                "version": 1,
                "reason": "Initial prompt",
                "is_active": False,
                "regression_passed": None,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "version": 2,
                "reason": "Improve urgency handling",
                "is_active": True,
                "regression_passed": True,
                "created_at": "2026-01-02T00:00:00+00:00",
            },
        ],
    )

    monkeypatch.setattr(
        "app.apis.prompts_api.load_prompt",
        lambda version: f"prompt content v{version}",
    )

    response = client.get("/prompts")

    assert response.status_code == 200

    data = response.json()

    assert data["active_version"] == 2
    assert len(data["prompts"]) == 2

    assert data["prompts"][0] == {
        "version": 1,
        "reason": "Initial prompt",
        "is_active": False,
        "regression_passed": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "content": "prompt content v1",
    }

    assert data["prompts"][1]["is_active"] is True
    assert data["prompts"][1]["regression_passed"] is True
    assert data["prompts"][1]["content"] == "prompt content v2"


def test_get_prompts_missing_file(monkeypatch):
    monkeypatch.setattr(
        "app.apis.prompts_api.list_prompt_versions",
        lambda: [
            {
                "version": 1,
                "reason": "Initial prompt",
                "is_active": True,
                "regression_passed": None,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
        ],
    )

    def missing_prompt(_: int):
        raise FileNotFoundError

    monkeypatch.setattr(
        "app.apis.prompts_api.load_prompt",
        missing_prompt,
    )

    response = client.get("/prompts")

    assert response.status_code == 200

    data = response.json()

    assert data["active_version"] == 1
    assert data["prompts"][0]["content"] is None
