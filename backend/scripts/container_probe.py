"""Temporary transport target mounted only by the isolated container check."""

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.usage import client_address

app = FastAPI()


@app.get("/api/health")
async def health():
    return {"status": "ok", "synthetic": True}


@app.get("/api/__container_identity")
async def identity(request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    peer = request.client.host
    return {
        "peer": peer,
        "forwarded": forwarded,
        "effective": client_address(peer, forwarded, get_settings().trusted_proxy_ips),
        "other_hints_absent": not request.headers.get("forwarded")
        and not request.headers.get("x-real-ip"),
    }


@app.get("/api/__container_stream")
async def stream():
    async def frames():
        yield 'event: status\ndata: {"synthetic":true}\n\n'
        await asyncio.sleep(65)
        yield 'event: done\ndata: {"synthetic":true}\n\n'

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
