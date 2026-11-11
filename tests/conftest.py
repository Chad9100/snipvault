import re

import pytest

from snipvault import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "t.db"), secret_key="test")


@pytest.fixture
def client(app):
    return app.test_client()


def token(client, path="/new"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture
def post(client):
    def _post(path, data=None, tok_path="/new", **kw):
        data = dict(data or {})
        data["csrf_token"] = token(client, tok_path)
        return client.post(path, data=data, **kw)
    return _post
