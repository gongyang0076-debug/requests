import requests


def test_get_user() -> None:
    response = requests.get("https://dummyjson.com/users/1", timeout=10)

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

    response = requests.post(
        "https://dummyjson.com/users/add",
        json=payload,
        timeout=10,
    )

    assert response.status_code == 201

    body = response.json()
    assert isinstance(body["id"], int)
    assert body["id"] > 0
    assert body["firstName"] == payload["firstName"]
    assert body["lastName"] == payload["lastName"]
    assert body["age"] == payload["age"]
