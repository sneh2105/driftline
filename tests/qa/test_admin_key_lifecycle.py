def _create_project(client, admin_key="dl_qa_admin"):
    return client.post(
        "/v1/admin/projects",
        json={"name": "lifecycle project"},
        headers={"X-Driftline-Admin-Key": admin_key},
    )


import pytest


@pytest.mark.xfail(strict=True, reason="BUG-3: unset admin key returns 401 instead of the specified 403")
def test_admin_endpoints_are_disabled_when_admin_key_is_unset(client, monkeypatch):
    monkeypatch.delenv("DRIFTLINE_ADMIN_KEY")

    created = client.post("/v1/admin/projects", json={"name": "blocked"})
    rotated = client.post("/v1/admin/projects/1/rotate-key")

    assert created.status_code == 403
    assert rotated.status_code == 403


def test_wrong_admin_key_is_rejected(client):
    response = _create_project(client, admin_key="wrong-admin-key")
    assert response.status_code == 401


def test_rotation_invalidates_old_key_and_returns_new_key_once(client):
    created = _create_project(client)
    assert created.status_code == 201
    initial_key = created.json()["api_key"]

    rotated = client.post(
        f"/v1/admin/projects/{created.json()['id']}/rotate-key",
        headers={"X-Driftline-Admin-Key": "dl_qa_admin"},
    )
    assert rotated.status_code == 200
    rotated_body = rotated.json()
    new_key = rotated_body["api_key"]
    assert new_key != initial_key
    assert "api_key" in rotated_body

    old_key_response = client.get("/v1/overview", headers={"X-Driftline-Key": initial_key})
    new_key_response = client.get("/v1/overview", headers={"X-Driftline-Key": new_key})
    assert old_key_response.status_code == 401
    assert new_key_response.status_code == 200

    rotated_again = client.post(
        f"/v1/admin/projects/{created.json()['id']}/rotate-key",
        headers={"X-Driftline-Admin-Key": "dl_qa_admin"},
    )
    assert rotated_again.status_code == 200
    assert rotated_again.json()["api_key"] != new_key

