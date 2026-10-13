import httpx

# Identify Lumen to the APIs we call (Open Library asks for this.)
USER_AGENT = "Lumen/0.1 (+https://github.com/ZhiouZhu2001/Lumen)"

# Give up on a slow API instead of making the user wait forever
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def make_http_client(
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    # `transport` is only passed in tests, to plug in a fake server.
    return httpx.AsyncClient(
        timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, transport=transport
    )
