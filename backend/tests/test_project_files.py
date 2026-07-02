"""Project file attachments (RFPs & BoQ templates) + the runnable-RFP feed."""

PDF = ("scope.pdf", b"%PDF-1.4 rfp", "application/pdf")
XLSX = ("template.xlsx", b"PK\x03\x04 boq", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _project(client, token, admin):
    return client.post("/projects", headers=token(admin), json={"name": "Tower"}).json()["id"]


def test_attach_list_download_delete(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    pid = _project(client, token, admin)

    up = client.post(f"/projects/{pid}/files?kind=rfp", headers=token(admin), files={"file": PDF})
    assert up.status_code == 200 and up.json()["kind"] == "rfp"
    fid = up.json()["id"]
    client.post(f"/projects/{pid}/files?kind=boq_template", headers=token(admin), files={"file": XLSX})

    files = client.get(f"/projects/{pid}/files", headers=token(admin)).json()
    assert {f["kind"] for f in files} == {"rfp", "boq_template"}

    dl = client.get(f"/projects/files/{fid}/download", headers=token(admin))
    assert dl.status_code == 200 and dl.content == PDF[1]

    assert client.delete(f"/projects/files/{fid}", headers=token(admin)).status_code == 200
    assert len(client.get(f"/projects/{pid}/files", headers=token(admin)).json()) == 1


def test_runnable_rfp_feed(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    pid = _project(client, token, admin)
    client.post(f"/projects/{pid}/files?kind=rfp", headers=token(admin), files={"file": PDF})
    client.post(f"/projects/{pid}/files?kind=boq_template", headers=token(admin), files={"file": XLSX})

    feed = client.get("/projects/rfp-files", headers=token(admin)).json()
    assert len(feed) == 1  # only the rfp file, not the template
    assert feed[0]["project_name"] == "Tower" and feed[0]["rfp_document_id"] is None


def test_only_rfp_kind_can_run(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    pid = _project(client, token, admin)
    tid = client.post(f"/projects/{pid}/files?kind=boq_template", headers=token(admin), files={"file": XLSX}).json()["id"]
    assert client.post(f"/projects/files/{tid}/run", headers=token(admin)).status_code == 400


def test_project_files_tenant_isolation(client, make_company, make_user, token):
    a, b = make_company("A"), make_company("B")
    admin_a = make_user(company=a, role="admin")
    admin_b = make_user(company=b, role="admin")
    b_pid = _project(client, token, admin_b)
    b_fid = client.post(f"/projects/{b_pid}/files?kind=rfp", headers=token(admin_b), files={"file": PDF}).json()["id"]

    assert client.get(f"/projects/files/{b_fid}/download", headers=token(admin_a)).status_code == 404
    assert client.delete(f"/projects/files/{b_fid}", headers=token(admin_a)).status_code == 404
    assert client.get("/projects/rfp-files", headers=token(admin_a)).json() == []
