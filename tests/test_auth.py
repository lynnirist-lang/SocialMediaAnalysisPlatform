import pytest


class TestAuth:
    """用户认证接口测试"""

    def test_register_and_login(self, client):
        username = "test_user_pytest"
        password = "testpass123"

        reg = client.post(
            "/api/auth/register",
            json={"username": username, "password": password, "email": "test@example.com"},
        )
        if reg.status_code == 200:
            pass
        elif reg.status_code == 400:
            assert "已存在" in reg.json().get("detail", "")

        login = client.post("/api/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200
        data = login.json()["data"]
        assert "access_token" in data
        assert data["username"] == username

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert me.status_code == 200
        assert me.json()["data"]["username"] == username
