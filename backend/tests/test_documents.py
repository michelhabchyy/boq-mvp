"""Document exchange access control: owner→company and company→subcontractor.
Recipients can read/download; only the sender can delete; no cross-tenant leak."""

PDF = ("contract.pdf", b"%PDF-1.4 signed", "application/pdf")


def test_owner_to_company_visibility(client, make_company, make_user, token):
    a, b = make_company("A"), make_company("B")
    owner = make_user(company=None, role="owner")
    admin_b = make_user(company=b, role="admin")
    admin_a = make_user(company=a, role="admin")

    # Owner uploads a document to company B.
    up = client.post(
        f"/documents/company/{b.id}",
        headers=token(owner),
        files={"file": PDF},
        data={"title": "NDA"},
    )
    assert up.status_code == 200
    doc_id = up.json()["id"]

    # B sees it in its inbox and can download the exact bytes.
    inbox = client.get("/documents/inbox", headers=token(admin_b)).json()
    assert any(d["id"] == doc_id for d in inbox)
    dl = client.get(f"/documents/{doc_id}/download", headers=token(admin_b))
    assert dl.status_code == 200 and dl.content == PDF[1]

    # Company A must NOT see or download B's document.
    assert all(d["id"] != doc_id for d in client.get("/documents/inbox", headers=token(admin_a)).json())
    assert client.get(f"/documents/{doc_id}/download", headers=token(admin_a)).status_code == 404


def test_recipient_company_cannot_delete_owner_document(client, make_company, make_user, token):
    b = make_company("B")
    owner = make_user(company=None, role="owner")
    admin_b = make_user(company=b, role="admin")
    doc_id = client.post(
        f"/documents/company/{b.id}", headers=token(owner), files={"file": PDF}
    ).json()["id"]

    # Recipient (B admin) cannot delete; the owner (sender) can.
    assert client.delete(f"/documents/{doc_id}", headers=token(admin_b)).status_code == 403
    assert client.delete(f"/documents/{doc_id}", headers=token(owner)).status_code == 200


def test_company_to_subcontractor_visibility(client, make_company, make_sub, make_user, token):
    co = make_company()
    sub1, sub2 = make_sub(co, "S1"), make_sub(co, "S2")
    admin = make_user(company=co, role="admin")
    sub1_user = make_user(company=co, role="subcontractor", subcontractor_id=sub1.id)
    sub2_user = make_user(company=co, role="subcontractor", subcontractor_id=sub2.id)

    doc_id = client.post(
        f"/documents/subcontractor/{sub1.id}",
        headers=token(admin),
        files={"file": PDF},
    ).json()["id"]

    # The target subcontractor sees & downloads it.
    my = client.get("/documents/my", headers=token(sub1_user)).json()
    assert any(d["id"] == doc_id for d in my)
    assert client.get(f"/documents/{doc_id}/download", headers=token(sub1_user)).status_code == 200

    # A different subcontractor cannot.
    assert all(d["id"] != doc_id for d in client.get("/documents/my", headers=token(sub2_user)).json())
    assert client.get(f"/documents/{doc_id}/download", headers=token(sub2_user)).status_code == 404

    # The subcontractor (recipient) cannot delete; the company (sender) can.
    assert client.delete(f"/documents/{doc_id}", headers=token(sub1_user)).status_code == 403
    assert client.delete(f"/documents/{doc_id}", headers=token(admin)).status_code == 200


def test_cannot_upload_to_other_companys_subcontractor(client, make_company, make_sub, make_user, token):
    a, b = make_company("A"), make_company("B")
    b_sub = make_sub(b, "BS")
    admin_a = make_user(company=a, role="admin")
    r = client.post(
        f"/documents/subcontractor/{b_sub.id}",
        headers=token(admin_a),
        files={"file": PDF},
    )
    assert r.status_code == 404  # A can't target B's subcontractor
