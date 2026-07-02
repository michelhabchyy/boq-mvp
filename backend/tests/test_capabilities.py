"""Company capability tree: Fields → Services → Sub-services (in-house/external)."""


def test_capability_tree_crud(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    h = token(admin)

    assert client.get("/capabilities", headers=h).json() == []

    tree = client.post("/capabilities/fields", headers=h, json={"name": "MEP"}).json()
    assert [f["name"] for f in tree] == ["MEP"]
    fid = tree[0]["id"]

    tree = client.post(f"/capabilities/fields/{fid}/services", headers=h, json={"name": "HVAC"}).json()
    sid = tree[0]["services"][0]["id"]
    assert tree[0]["services"][0]["name"] == "HVAC"

    tree = client.post(f"/capabilities/services/{sid}/subservices", headers=h, json={"name": "Ductwork", "in_house": True}).json()
    tree = client.post(f"/capabilities/services/{sid}/subservices", headers=h, json={"name": "Chillers", "in_house": False}).json()
    subs = tree[0]["services"][0]["sub_services"]
    assert {s["name"]: s["in_house"] for s in subs} == {"Ductwork": True, "Chillers": False}

    # flip a sub-service to external
    ss = [s for s in subs if s["name"] == "Ductwork"][0]["id"]
    tree = client.patch(f"/capabilities/subservices/{ss}", headers=h, json={"in_house": False}).json()
    assert all(s["in_house"] is False for s in tree[0]["services"][0]["sub_services"])

    # deleting the field cascades everything
    tree = client.delete(f"/capabilities/fields/{fid}", headers=h).json()
    assert tree == []


def test_capability_reviewer_readonly(client, make_company, make_user, token):
    co = make_company()
    reviewer = make_user(company=co, role="reviewer")
    assert client.get("/capabilities", headers=token(reviewer)).status_code == 200
    assert client.post("/capabilities/fields", headers=token(reviewer), json={"name": "X"}).status_code == 403


def test_capability_tenant_isolation(client, make_company, make_user, token):
    a, b = make_company("A"), make_company("B")
    admin_a = make_user(company=a, role="admin")
    admin_b = make_user(company=b, role="admin")
    b_field = client.post("/capabilities/fields", headers=token(admin_b), json={"name": "Civil"}).json()[0]["id"]

    # A can't rename or delete B's field, and never sees it
    assert client.patch(f"/capabilities/fields/{b_field}", headers=token(admin_a), json={"name": "x"}).status_code == 404
    assert client.get("/capabilities", headers=token(admin_a)).json() == []
