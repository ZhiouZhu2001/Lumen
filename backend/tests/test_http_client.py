import httpx

from app.http_client import USER_AGENT, make_http_client


async def test_client_sends_user_agent() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["user_agent"] = request.headers["User-Agent"]
        return httpx.Response(200)

    async with make_http_client(transport=httpx.MockTransport(handler)) as client:
        await client.get("https://openlibrary.org/search.json")

    assert seen["user_agent"] == USER_AGENT


def test_client_has_a_timeout() -> None:
    client = make_http_client()
    assert client.timeout.read == 10.0
    assert client.timeout.connect == 5.0
