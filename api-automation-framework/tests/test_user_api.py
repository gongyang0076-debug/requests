from api.user_api import UserApi


def test_get_user(user_api: UserApi) -> None:
    response = user_api.get_user(1)

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == 1
    assert isinstance(body["firstName"], str)
    assert body["firstName"]
    assert isinstance(body["email"], str)
    assert "@" in body["email"]


def test_create_user(user_api: UserApi) -> None:
    payload: dict[str, object] = {
        "firstName": "Tom",
        "lastName": "Tester",
        "age": 21,
    }

    response = user_api.create_user(payload)

    assert response.status_code == 201

    body = response.json()
    assert isinstance(body["id"], int)
    assert body["id"] > 0
    assert body["firstName"] == payload["firstName"]
    assert body["lastName"] == payload["lastName"]
    assert body["age"] == payload["age"]


def test_update_user(user_api: UserApi) -> None:
    payload = {"lastName": "Updated"}

    response = user_api.update_user(2, payload)

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == 2
    assert body["lastName"] == payload["lastName"]


def test_delete_user(user_api: UserApi) -> None:
    response = user_api.delete_user(1)

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == 1
    assert body["isDeleted"] is True
    assert isinstance(body["deletedOn"], str)
    assert body["deletedOn"]
