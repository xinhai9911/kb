"""单元/冒烟测试（对应 [[entities/CI_CD 流水线实战]] §5 / [[concepts/CI_CD与测试策略]] §3）"""
import pytest
from app import app as flask_app


@pytest.fixture
def client():
    return flask_app.test_client()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.data == b"ok"


def test_order(client):
    r = client.post("/order", json={"user_id": "u1"})
    assert r.status_code == 200
    assert r.get_json()["user_id"] == "u1"
