def test_missing_and_invalid_api_keys_are_rejected(client):
    key = client.headers.pop("X-Driftline-Key")
    try:
        missing = client.get("/v1/overview")
    finally:
        client.headers["X-Driftline-Key"] = key

    invalid = client.get("/v1/overview", headers={"X-Driftline-Key": "not-a-valid-key"})
    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_authorization_bearer_key_is_accepted(client):
    response = client.get("/v1/overview", headers={"Authorization": "Bearer dl_qa_test"})
    assert response.status_code == 200


def test_project_key_cannot_read_another_projects_data(client):
    created = client.post(
        "/v1/admin/projects",
        json={"name": "second project"},
        headers={"X-Driftline-Admin-Key": "dl_qa_admin"},
    )
    assert created.status_code == 201
    second_key = created.json()["api_key"]

    second_event = {
        "approver": "private reviewer",
        "action": "private transfer",
        "decision": "approve",
        "seconds": 3,
    }
    ingested = client.post(
        "/v1/approvals",
        json=second_event,
        headers={"X-Driftline-Key": second_key},
    )
    assert ingested.status_code == 201

    first_project_view = client.get("/v1/overview")
    second_project_view = client.get("/v1/overview", headers={"X-Driftline-Key": second_key})
    assert first_project_view.status_code == second_project_view.status_code == 200
    assert first_project_view.json()["org"]["n"] == 0
    assert second_project_view.json()["org"]["n"] == 1
