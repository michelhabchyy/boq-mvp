"""TOTP two-factor: enrolment, login gating, and disable."""

import pyotp


def test_twofa_enrol_login_and_disable(client, make_company, make_user, token):
    co = make_company()
    u = make_user(company=co, role="admin", password="pw-secret-123")
    hdr = token(u)

    # Off by default.
    assert client.get("/auth/2fa/status", headers=hdr).json()["enabled"] is False

    # Setup returns a secret + QR; not yet enabled.
    setup = client.post("/auth/2fa/setup", headers=hdr).json()
    assert setup["secret"] and setup["qr_svg"].startswith("<")
    totp = pyotp.TOTP(setup["secret"])

    # A wrong code is rejected; the correct one enables it.
    assert client.post("/auth/2fa/verify", headers=hdr, json={"code": "000000"}).status_code == 400
    ok = client.post("/auth/2fa/verify", headers=hdr, json={"code": totp.now()})
    assert ok.status_code == 200 and ok.json()["enabled"] is True

    # Login now requires the second factor.
    r1 = client.post("/auth/login", json={"username": u.username, "password": "pw-secret-123"})
    assert r1.status_code == 200 and r1.json()["mfa_required"] is True
    assert r1.json().get("access_token") is None

    # Wrong OTP -> 401; correct OTP -> token issued.
    bad = client.post("/auth/login", json={"username": u.username, "password": "pw-secret-123", "otp": "000000"})
    assert bad.status_code == 401
    good = client.post(
        "/auth/login",
        json={"username": u.username, "password": "pw-secret-123", "otp": totp.now()},
    )
    assert good.status_code == 200 and good.json()["access_token"]

    # Disabling requires a valid code.
    assert client.post("/auth/2fa/disable", headers=hdr, json={"code": "000000"}).status_code == 400
    off = client.post("/auth/2fa/disable", headers=hdr, json={"code": totp.now()})
    assert off.status_code == 200 and off.json()["enabled"] is False


def test_login_unaffected_without_2fa(client, make_company, make_user):
    co = make_company()
    u = make_user(company=co, role="reviewer", password="pw-secret-123")
    r = client.post("/auth/login", json={"username": u.username, "password": "pw-secret-123"})
    assert r.status_code == 200 and r.json()["access_token"] and r.json()["mfa_required"] is False
