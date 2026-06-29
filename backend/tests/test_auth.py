"""Authentication & session behaviour."""


def test_login_success(client, make_company, make_user):
    co = make_company()
    make_user(company=co, role="admin", password="pw-secret-123")
    # find the username we just made
    # (the factory randomises it, so log in via a fresh known user)
    u = make_user(company=co, role="admin", password="pw-secret-123")
    r = client.post("/auth/login", json={"username": u.username, "password": "pw-secret-123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["role"] == "admin"


def test_login_wrong_password(client, make_company, make_user):
    co = make_company()
    u = make_user(company=co, role="admin", password="pw-secret-123")
    r = client.post("/auth/login", json={"username": u.username, "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"username": "ghost_user_xyz", "password": "x"})
    assert r.status_code == 401


def test_protected_endpoint_requires_token(client):
    r = client.get("/catalog")
    assert r.status_code in (401, 403)  # no bearer token


def test_admin_can_list_catalog(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    r = client.get("/catalog", headers=token(admin))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_disabled_user_is_blocked(client, make_company, make_user, token):
    co = make_company()
    u = make_user(company=co, role="admin", active=False)
    r = client.get("/catalog", headers=token(u))
    assert r.status_code == 401


def test_user_of_disabled_company_is_blocked(client, db, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    co.is_active = False
    db.flush()
    r = client.get("/catalog", headers=token(admin))
    assert r.status_code == 401
