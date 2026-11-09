"""Compare direct/proxied delayed SSE without model, catalog or database calls.

The normal backend must be stopped. This temporary loopback diagnostic server
uses its port only while the check runs; no route is added to the application.
"""

import argparse
import asyncio
import hashlib
import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse


async def run(frontend: str, port: int, delay: float, output: Path):
    assert not output.exists(), "Choose a new evidence path"
    app = FastAPI()

    @app.get("/api/__stream_probe")
    async def probe():
        async def events():
            yield 'event: status\ndata: {"diagnostic":true}\n\n'
            await asyncio.sleep(delay)
            yield 'event: done\ndata: {"diagnostic":true}\n\n'

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    sock = socket.socket()
    sock.bind(("127.0.0.1", port))
    server = uvicorn.Server(
        uvicorn.Config(app, access_log=False, log_level="error", proxy_headers=False)
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))

    async def read(origin):
        started = perf_counter()
        first = None
        names = []
        error = None
        try:
            async with (
                httpx.AsyncClient(timeout=delay + 10) as client,
                client.stream("GET", origin + "/api/__stream_probe") as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        if first is None:
                            first = round((perf_counter() - started) * 1000, 2)
                        names.append(line[6:].strip())
        except httpx.HTTPError as exc:
            error = type(exc).__name__
        return {
            "events": names,
            "first_frame_ms": first,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "error_kind": error,
            "done_seen": names == ["status", "done"],
        }

    try:
        async with asyncio.timeout(15):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Probe server did not start")
                await asyncio.sleep(0.05)
        direct, proxied = await asyncio.gather(
            read(f"http://127.0.0.1:{port}"), read(frontend)
        )
        config = Path(__file__).resolve().parents[2] / "frontend/next.config.ts"
        report = {
            "target": "synthetic_delayed_sse_proxy_comparison",
            "full_suite": False,
            "checked_at": datetime.now(UTC).isoformat(),
            "silent_interval_seconds": delay,
            "model_requests": 0,
            "catalog_requests": 0,
            "database_writes": 0,
            "frontend_config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "direct": direct,
            "frontend": proxied,
            "passed": direct["done_seen"] and proxied["done_seen"],
            "limitation": "This deterministic protocol probe is not a real recommendation or the 20-case merge gate.",
        }
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
        return 0 if report["passed"] else 1
    finally:
        server.should_exit = True
        await task
        sock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", default="http://127.0.0.1:3000")
    parser.add_argument("--backend-port", type=int, default=8001)
    parser.add_argument("--delay", type=float, default=35)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = urlsplit(args.frontend)
    if (
        url.scheme != "http"
        or url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
        or not 0 < args.delay < 60
        or not 0 < args.backend_port < 65536
    ):
        parser.error(
            "Use a loopback HTTP origin, valid port and delay below the backend's 60-second deadline"
        )
    return asyncio.run(run(args.frontend, args.backend_port, args.delay, args.output))


if __name__ == "__main__":
    raise SystemExit(main())
