from urllib.parse import quote

import pytest


@pytest.mark.parametrize(
    "path,valid_days,invalid_days",
    [
        ("/v1/overview", [1, 365], [0, 366]),
        ("/v1/digest", [1, 90], [0, 91]),
    ],
)
def test_days_parameter_enforces_documented_bounds(client, path, valid_days, invalid_days):
    for days in valid_days:
        assert client.get(path, params={"days": days}).status_code == 200
    for days in invalid_days:
        assert client.get(path, params={"days": days}).status_code == 422


def test_unknown_approver_returns_404(client):
    response = client.get("/v1/approvers/not-a-known-reviewer")

    assert response.status_code == 404


def test_approver_name_with_special_characters_is_readable(client):
    name = "qa reviewer + & # 東京"
    ingested = client.post(
        "/v1/approvals",
        json={
            "approver": name,
            "action": "review transfer",
            "decision": "approve",
            "seconds": 3,
        },
    )
    assert ingested.status_code == 201

    response = client.get(f"/v1/approvers/{quote(name, safe='')}")

    assert response.status_code == 200
    assert response.json()["approver"] == name
