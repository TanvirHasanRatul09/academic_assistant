import httpx

from app.services.classroom.client import ClassroomClient, ClassroomError


def test_pagination_follows_next_page_token() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"courses": [{"id": "1"}], "nextPageToken": "next"})
        return httpx.Response(200, json={"courses": [{"id": "2"}]})

    transport = httpx.MockTransport(handler)
    client = ClassroomClient("private-token", httpx.Client(transport=transport))

    ids = [item["id"] for page in client.pages("/courses", "courses") for item in page]

    assert ids == ["1", "2"]
    assert requests[1].url.params["pageToken"] == "next"


def test_authorization_failure_uses_safe_error_code() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(401))
    client = ClassroomClient("private-token", httpx.Client(transport=transport))

    try:
        client.get("/courses")
    except ClassroomError as exc:
        assert exc.code == "authorization_revoked"
    else:
        raise AssertionError("expected ClassroomError")


def test_client_records_request_and_pagination_metrics() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"courses": []}))
    client = ClassroomClient("private-token", httpx.Client(transport=transport))
    list(client.pages("/courses", "courses"))
    assert client.request_count == 1
    assert client.page_count == 1
    assert client.request_seconds >= 0


def test_timeout_retries_and_reports_safe_error(monkeypatch) -> None:
    monkeypatch.setattr("app.services.classroom.client.time.sleep", lambda _seconds: None)

    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow provider")

    client = ClassroomClient("private-token", httpx.Client(transport=httpx.MockTransport(timeout)))
    try:
        client.get("/courses")
    except ClassroomError as exc:
        assert exc.code == "provider_timeout"
        assert exc.retryable
        assert client.request_count == 3
    else:
        raise AssertionError("expected ClassroomError")


def test_pagination_can_be_bounded_without_reporting_an_error() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"courses": [{"id": str(len(requests))}], "nextPageToken": "more"},
        )

    client = ClassroomClient("private-token", httpx.Client(transport=httpx.MockTransport(handler)))
    pages = list(client.pages("/courses", "courses", max_pages=2))

    assert [[item["id"] for item in page] for page in pages] == [["1"], ["2"]]
    assert client.request_count == 2
    assert client.page_count == 2
