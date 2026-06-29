"""The most important suite: one company must never reach another's data,
and roles must be enforced. These guard against IDOR / privilege bugs."""


def test_catalog_list_is_scoped(client, make_company, make_user, make_item, token):
    a, b = make_company("A"), make_company("B")
    make_item(a, code="A-1")
    make_item(b, code="B-1")
    admin_a = make_user(company=a, role="admin")

    codes = [i["item_code"] for i in client.get("/catalog", headers=token(admin_a)).json()]
    assert "A-1" in codes
    assert "B-1" not in codes  # B's item must not leak to A


def test_cannot_edit_other_companys_item(client, make_company, make_user, make_item, token):
    a, b = make_company("A"), make_company("B")
    b_item = make_item(b, code="B-9")
    admin_a = make_user(company=a, role="admin")

    r = client.patch(f"/catalog/{b_item.id}", headers=token(admin_a), json={"unit_cost": 999})
    assert r.status_code == 404  # not found *for A*


def test_cannot_delete_other_companys_item(client, make_company, make_user, make_item, token):
    a, b = make_company("A"), make_company("B")
    b_item = make_item(b, code="B-8")
    admin_a = make_user(company=a, role="admin")

    r = client.delete(f"/catalog/item/{b_item.id}", headers=token(admin_a))
    assert r.status_code == 404


def test_cannot_read_other_companys_rfp(client, make_company, make_user, make_rfp, token):
    a, b = make_company("A"), make_company("B")
    b_rfp = make_rfp(b)
    admin_a = make_user(company=a, role="admin")

    assert client.get(f"/rfps/{b_rfp.id}", headers=token(admin_a)).status_code == 404
    assert client.delete(f"/rfps/{b_rfp.id}", headers=token(admin_a)).status_code == 404


def test_reviewer_cannot_write_catalog(client, make_company, make_user, token):
    co = make_company()
    reviewer = make_user(company=co, role="reviewer")
    r = client.post("/catalog/item", headers=token(reviewer), json={"description_en": "x", "unit": "m", "unit_cost": 1})
    assert r.status_code == 403  # admin-only action


def test_subcontractor_cannot_access_company_catalog(client, make_company, make_sub, make_user, token):
    co = make_company()
    sub = make_sub(co)
    sub_user = make_user(company=co, role="subcontractor", subcontractor_id=sub.id)
    assert client.get("/catalog", headers=token(sub_user)).status_code == 403


def test_subcontractor_only_sees_own_items(client, make_company, make_sub, make_user, make_item, token):
    co = make_company()
    sub1, sub2 = make_sub(co, "S1"), make_sub(co, "S2")
    make_item(co, subcontractor_id=sub1.id, code="S1-1")
    make_item(co, subcontractor_id=sub2.id, code="S2-1")
    u1 = make_user(company=co, role="subcontractor", subcontractor_id=sub1.id)

    codes = [i["item_code"] for i in client.get("/my-items", headers=token(u1)).json()]
    assert codes == ["S1-1"]  # never S2's


def test_owner_impersonation_and_header_ignored_for_nonowners(
    client, make_company, make_user, make_item, token
):
    a, b = make_company("A"), make_company("B")
    make_item(a, code="A-X")
    make_item(b, code="B-X")
    owner = make_user(company=None, role="owner")
    admin_a = make_user(company=a, role="admin")

    # Owner impersonates B via the header -> sees only B's catalog.
    owner_codes = [i["item_code"] for i in client.get("/catalog", headers=token(owner, company_id=b.id)).json()]
    assert owner_codes == ["B-X"]

    # A non-owner who *forges* X-Company-Id=B is still scoped to their own company.
    a_codes = [i["item_code"] for i in client.get("/catalog", headers=token(admin_a, company_id=b.id)).json()]
    assert "A-X" in a_codes and "B-X" not in a_codes


def test_owner_without_company_header_is_rejected(client, make_user, token):
    owner = make_user(company=None, role="owner")
    # Estimator-side endpoints need a company context for the owner.
    assert client.get("/catalog", headers=token(owner)).status_code == 400
