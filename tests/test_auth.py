import re

import pytest

from snipvault import create_app
from snipvault.cli import main


@pytest.fixture
def locked(tmp_path):
    return create_app(str(tmp_path / "a.db"), secret_key="test", token="s3cret")


def _csrf(client):
    html = client.get("/login").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_no_token_means_open(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/tags").status_code == 200


def test_page_redirects_to_login(locked):
    r = locked.test_client().get("/?q=x")
    assert r.status_code == 302
    assert "/login?next=" in r.headers["Location"]


def test_api_needs_bearer(locked):
    c = locked.test_client()
    r = c.get("/api/snippets")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert r.get_json() == {"error": "authentication required"}
    assert c.get("/api/snippets", headers={"Authorization": "Bearer nope"}).status_code == 401
    ok = c.get("/api/snippets", headers={"Authorization": "bearer s3cret"})
    assert ok.status_code == 200


def test_api_write_with_bearer(locked):
    r = locked.test_client().post(
        "/api/snippets", json={"title": "t", "body": "b"},
        headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 201


def test_login_flow(locked):
    c = locked.test_client()
    bad = c.post("/login", data={"token": "wrong", "csrf_token": _csrf(c)})
    assert bad.status_code == 401
    good = c.post("/login", data={"token": "s3cret", "next": "/new",
                                  "csrf_token": _csrf(c)})
    assert good.status_code == 302 and good.headers["Location"] == "/new"
    assert c.get("/").status_code == 200
    # a signed-in browser session also unlocks the API
    assert c.get("/api/tags").status_code == 200


def test_login_does_not_redirect_off_site(locked):
    c = locked.test_client()
    r = c.post("/login", data={"token": "s3cret", "next": "//evil.example/x",
                               "csrf_token": _csrf(c)})
    assert r.headers["Location"] == "/"


def test_logout(locked):
    c = locked.test_client()
    c.post("/login", data={"token": "s3cret", "csrf_token": _csrf(c)})
    html = c.get("/").get_data(as_text=True)
    c.post("/logout", data={"csrf_token": _csrf(c)})
    assert c.get("/").status_code == 302
    assert html


def test_static_stays_public(locked):
    assert locked.test_client().get("/static/style.css").status_code == 200


def test_env_token(tmp_path, monkeypatch):
    monkeypatch.setenv("SNIPVAULT_TOKEN", "fromenv")
    app = create_app(str(tmp_path / "e.db"))
    assert app.test_client().get("/api/tags").status_code == 401


def test_cli_token_announced(tmp_path, monkeypatch, capsys):
    import snipvault.app as appmod
    seen = {}

    def fake_create(db_path, token=None):
        seen["token"] = token

        class A:
            def run(self, **kw):
                pass
        return A()
    monkeypatch.setattr(appmod, "create_app", fake_create)
    monkeypatch.delenv("SNIPVAULT_TOKEN", raising=False)
    assert main(["serve", "--db", str(tmp_path / "c.db"), "--token", "abc"]) == 0
    assert seen["token"] == "abc"
    assert "access token required" in capsys.readouterr().out
