from api.user_api import UserApi
from common.http_client import HttpClient


def test_get_user() -> None:
    with HttpClient("https://dummyjson.com", timeout=10) as client:
        user_api = UserApi(client)
        response = user_api.get_user(1)

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == 1
    assert isinstance(body["firstName"], str)
    assert body["firstName"]
    assert isinstance(body["email"], str)
    assert "@" in body["email"]


def test_create_user() -> None:
    payload: dict[str, object] = {
        "firstName": "Tom",
        "lastName": "Tester",
        "age": 21,
    }

    with HttpClient("https://dummyjson.com", timeout=10) as client:
        user_api = UserApi(client)
        response = user_api.create_user(payload)

    assert response.status_code == 201

    body = response.json()
    assert isinstance(body["id"], int)
    assert body["id"] > 0
    assert body["firstName"] == payload["firstName"]
    assert body["lastName"] == payload["lastName"]
    assert body["age"] == payload["age"]


def test_update_user() -> None:
    payload = {"lastName": "Updated"}

    with HttpClient("https://dummyjson.com", timeout=10) as client:
        user_api = UserApi(client)
        response = user_api.update_user(2, payload)

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == 2
    assert body["lastName"] == payload["lastName"]


def test_delete_user() -> None:
    with HttpClient("https://dummyjson.com", timeout=10) as client:
        user_api = UserApi(client)
        response = user_api.delete_user(1)

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == 1
    assert body["isDeleted"] is True
    assert isinstance(body["deletedOn"], str)
    assert body["deletedOn"]
