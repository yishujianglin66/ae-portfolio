"""User 路由的端到端测试（经 ASGI，不启真实端口）。"""
from app.schemas.user import UserCreate

BASE = "/api/v1/users"


async def _create(client, email: str, name: str = "N"):
    return await client.post(
        BASE, json={"email": email, "name": name, "password": "supersecret"}
    )


async def test_create_and_get_user(client):
    r = await _create(client, "alice@example.com", "Alice")
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data  # 密码永不出网
    uid = data["id"]

    r2 = await client.get(f"{BASE}/{uid}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "Alice"


async def test_list_users_pagination(client):
    for i in range(3):
        await _create(client, f"u{i}@example.com", f"U{i}")
    r = await client.get(BASE, params={"page": 1, "size": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["size"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 2


async def test_duplicate_email_conflict(client):
    await _create(client, "bob@example.com", "Bob")
    r = await _create(client, "bob@example.com", "Bob2")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


async def test_get_missing_user_404(client):
    r = await client.get(f"{BASE}/9999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


async def test_update_user(client):
    uid = (await _create(client, "carol@example.com", "Carol")).json()["id"]
    r = await client.patch(f"{BASE}/{uid}", json={"name": "Caroline", "is_active": False})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Caroline"
    assert body["is_active"] is False


async def test_delete_user(client):
    uid = (await _create(client, "dave@example.com", "Dave")).json()["id"]
    r = await client.delete(f"{BASE}/{uid}")
    assert r.status_code == 204
    r2 = await client.get(f"{BASE}/{uid}")
    assert r2.status_code == 404


async def test_validation_error(client):
    # 邮箱格式错 + 缺 password => 422
    r = await client.post(BASE, json={"email": "not-an-email", "name": "X"})
    assert r.status_code == 422
