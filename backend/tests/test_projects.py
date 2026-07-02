"""Project pipeline: creation, status transitions with history, role gating,
and tenant isolation."""


def _new(client, token, admin, **over):
    body = {"name": "Riyadh Tower MEP", "industry": "Electrical", "awarded_from": "ACME Dev", **over}
    return client.post("/projects", headers=token(admin), json=body)


def test_create_project_defaults_to_lead_and_logs_event(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    r = _new(client, token, admin)
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["status"] == "lead"

    detail = client.get(f"/projects/{pid}", headers=token(admin)).json()
    assert detail["project"]["name"] == "Riyadh Tower MEP"
    assert len(detail["events"]) == 1 and detail["events"][0]["to_status"] == "lead"


def test_status_pipeline_records_history(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    pid = _new(client, token, admin).json()["id"]

    for s in ["bidding", "shortlisted", "awarded"]:
        r = client.post(f"/projects/{pid}/status", headers=token(admin), json={"status": s, "note": f"moved to {s}"})
        assert r.status_code == 200

    detail = client.get(f"/projects/{pid}", headers=token(admin)).json()
    assert detail["project"]["status"] == "awarded"
    # created + 3 transitions = 4 events, newest first
    assert [e["to_status"] for e in detail["events"]] == ["awarded", "shortlisted", "bidding", "lead"]


def test_invalid_status_rejected(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    pid = _new(client, token, admin).json()["id"]
    r = client.post(f"/projects/{pid}/status", headers=token(admin), json={"status": "nonsense"})
    assert r.status_code == 400


def test_summary_counts(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    _new(client, token, admin)
    pid2 = _new(client, token, admin, name="Villa").json()["id"]
    client.post(f"/projects/{pid2}/status", headers=token(admin), json={"status": "completed"})

    s = client.get("/projects/summary", headers=token(admin)).json()
    assert s["lead"] == 1 and s["completed"] == 1


def test_reviewer_cannot_create(client, make_company, make_user, token):
    co = make_company()
    reviewer = make_user(company=co, role="reviewer")
    assert _new(client, token, reviewer).status_code == 403
    # ...but can read the list
    assert client.get("/projects", headers=token(reviewer)).status_code == 200


def test_project_tenant_isolation(client, make_company, make_user, token):
    a, b = make_company("A"), make_company("B")
    admin_a = make_user(company=a, role="admin")
    admin_b = make_user(company=b, role="admin")
    b_pid = _new(client, token, admin_b).json()["id"]

    assert client.get(f"/projects/{b_pid}", headers=token(admin_a)).status_code == 404
    assert client.post(f"/projects/{b_pid}/status", headers=token(admin_a), json={"status": "lost"}).status_code == 404
    assert client.delete(f"/projects/{b_pid}", headers=token(admin_a)).status_code == 404
    # A's list never shows B's project
    assert all(p["id"] != b_pid for p in client.get("/projects", headers=token(admin_a)).json())
