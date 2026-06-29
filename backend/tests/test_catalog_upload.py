"""Bulk catalog upload: works without an item_code column (codes auto-assigned),
surfaces a usable result, and offers a fillable template."""


def test_upload_without_item_code_autogenerates(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    csv = b"description_en,unit,cost,brand\nLED light,Each,42.50,Philips\nCable 2.5mm,m,3.20,Nexans\n"

    r = client.post(
        "/catalog/upload?skip_invalid=true",
        headers=token(admin),
        files={"file": ("sheet.csv", csv, "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["loaded"] == 2

    items = client.get("/catalog", headers=token(admin)).json()
    led = [i for i in items if i["description_en"] == "LED light"]
    assert led and led[0]["item_code"].startswith("ITM-")  # system-assigned code
    assert led[0]["unit_cost"] == 42.5


def test_upload_rejects_sheet_without_cost(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    csv = b"description_en,unit\nThing,Each\n"  # no unit_cost column
    r = client.post(
        "/catalog/upload?skip_invalid=true",
        headers=token(admin),
        files={"file": ("bad.csv", csv, "text/csv")},
    )
    assert r.status_code == 400
    assert "unit_cost" in r.json()["detail"]


def test_template_download(client, make_company, make_user, token):
    co = make_company()
    admin = make_user(company=co, role="admin")
    r = client.get("/catalog/template.xlsx", headers=token(admin))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # a real .xlsx (zip) file
