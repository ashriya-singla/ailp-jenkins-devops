"""Behaviour and authorization tests for AILP."""

import pytest

from ailp import create_app

STUDENT = "s" * 32
EDUCATOR = "e" * 32
S = {"Authorization": f"Bearer {STUDENT}"}
E = {"Authorization": f"Bearer {EDUCATOR}"}
PAYLOAD = {
    "source": "Chat 1",
    "prompt": "Explain testing",
    "response": "Use assertions",
    "consent": True,
}


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.db"),
            "STUDENT_TOKEN": STUDENT,
            "EDUCATOR_TOKEN": EDUCATOR,
            "VERSION": "test",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_and_ui(client):
    assert client.get("/health").json == {"status": "ok", "version": "test"}
    page = client.get("/")
    assert b"Educator Evidence View" in page.data
    assert "script-src 'self'" in page.headers["Content-Security-Policy"]
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert b"ailp_up 1" in client.get("/metrics").data


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/evidence"),
        ("post", "/api/evidence"),
        ("get", "/api/privacy"),
        ("get", "/api/passport"),
    ],
)
def test_requires_auth(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_import_and_decision_persist(app, client):
    record_id = client.post("/api/evidence", headers=S, json=PAYLOAD).json["id"]
    assert (
        client.put(
            f"/api/evidence/{record_id}/decision",
            headers=S,
            json={"decision": "Modified", "reasoning": "Verified and corrected"},
        ).status_code
        == 200
    )
    second = create_app(dict(app.config)).test_client()
    assert second.get("/api/evidence", headers=S).json[0]["decision"] == "Modified"
    assert second.get("/api/passport", headers=S).json["evidence"][0]["source"] == "Chat 1"


def test_consent_grant_and_revoke(client):
    client.post("/api/evidence", headers=S, json=PAYLOAD)
    assert client.get("/api/passport", headers=E).status_code == 403
    assert client.put("/api/privacy", headers=S, json={"shared": True}).json["shared"] is True
    assert len(client.get("/api/passport", headers=E).json["evidence"]) == 1
    client.put("/api/privacy", headers=S, json={"shared": False})
    assert client.get("/api/passport", headers=E).status_code == 403


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/evidence"),
        ("post", "/api/evidence"),
        ("put", "/api/privacy"),
        ("put", "/api/evidence/1/decision"),
        ("delete", "/api/evidence/1"),
    ],
)
def test_educator_cannot_mutate(client, method, path):
    assert getattr(client, method)(path, headers=E, json=PAYLOAD).status_code == 403


@pytest.mark.parametrize(
    "data",
    [
        {},
        {**PAYLOAD, "consent": False},
        {**PAYLOAD, "consent": "true"},
        {**PAYLOAD, "source": " "},
        {**PAYLOAD, "response": 1},
        {**PAYLOAD, "prompt": "x" * 4001},
        [],
    ],
)
def test_invalid_import(client, data):
    assert client.post("/api/evidence", headers=S, json=data).status_code == 400


@pytest.mark.parametrize("decision", ["Accepted", "Modified", "Rejected"])
def test_decision_options(client, decision):
    client.post("/api/evidence", headers=S, json=PAYLOAD)
    assert (
        client.put(
            "/api/evidence/1/decision",
            headers=S,
            json={"decision": decision, "reasoning": "I evaluated it"},
        ).status_code
        == 200
    )


def test_invalid_decision_and_missing_record(client):
    assert (
        client.put(
            "/api/evidence/1/decision",
            headers=S,
            json={"decision": "Automatic score", "reasoning": "No"},
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/api/evidence/999/decision",
            headers=S,
            json={"decision": "Accepted", "reasoning": "Yes"},
        ).status_code
        == 404
    )


@pytest.mark.parametrize("data", [{"shared": 1}, {"shared": "false"}, {}, []])
def test_invalid_privacy(client, data):
    assert client.put("/api/privacy", headers=S, json=data).status_code == 400


def test_delete_and_sql_injection_literal(client):
    attack = "'); DROP TABLE evidence; --"
    client.post("/api/evidence", headers=S, json={**PAYLOAD, "source": attack})
    assert client.get("/api/evidence", headers=S).json[0]["source"] == attack
    assert client.delete("/api/evidence/1", headers=S).status_code == 204
    assert client.get("/api/evidence", headers=S).json == []
    assert client.delete("/api/evidence/1", headers=S).status_code == 404


def test_oversized_body(client):
    assert client.post("/api/evidence", headers=S, json={"prompt": "x" * 40000}).status_code == 413


@pytest.mark.parametrize("tokens", [("", ""), (STUDENT, STUDENT)])
def test_rejects_insecure_config(tmp_path, tokens):
    with pytest.raises(ValueError):
        create_app(
            {
                "DATABASE": str(tmp_path / "fail.db"),
                "STUDENT_TOKEN": tokens[0],
                "EDUCATOR_TOKEN": tokens[1],
            }
        )
