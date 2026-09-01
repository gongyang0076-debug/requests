from unittest.mock import Mock, call, patch

from common.http_client import HttpClient


def test_request_builds_url_and_passes_request_options() -> None:
    fake_response = Mock()

    with HttpClient("https://example.com/", timeout=5) as client:
        with patch(
            "common.http_client.requests.Session.request",
            return_value=fake_response,
        ) as session_request:
            response = client.request(
                "post",
                "/users",
                headers={"X-Request-ID": "request-1"},
                cookies={"session": "cookie-value"},
                params={"source": "test"},
                json={"name": "Tom"},
                data=None,
            )

    assert response is fake_response
    session_request.assert_called_once_with(
        method="POST",
        url="https://example.com/users",
        timeout=5,
        headers={"X-Request-ID": "request-1"},
        cookies={"session": "cookie-value"},
        params={"source": "test"},
        json={"name": "Tom"},
        data=None,
    )


def test_http_method_helpers_delegate_to_request() -> None:
    with HttpClient("https://example.com") as client:
        with patch.object(client, "request") as request:
            client.get("/users", params={"limit": 1})
            client.post("/users", json={"name": "Tom"})
            client.put("/users/1", json={"name": "Jerry"})
            client.patch("/users/1", json={"age": 22})
            client.delete("/users/1")

    assert request.call_args_list == [
        call("GET", "/users", params={"limit": 1}),
        call("POST", "/users", json={"name": "Tom"}),
        call("PUT", "/users/1", json={"name": "Jerry"}),
        call("PATCH", "/users/1", json={"age": 22}),
        call("DELETE", "/users/1"),
    ]
