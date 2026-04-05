"""Reverse-proxy for user containers.

All requests to /u/{user_id}/... are forwarded to the user's BlogPilot container
via the internal Docker network.  WebSocket connections to /u/{user_id}/ws are
similarly bridged.

Authentication: every request must carry the container's api_token either via
Bearer header (HTTP) or ?token= query param (WebSocket). The token is verified
against the container record for the given user_id, preventing IDOR attacks.
"""

import asyncio
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from bp_platform.models.database import Container, get_db

logger = logging.getLogger("platform.proxy")
router = APIRouter(tags=["proxy"])

# Headers that must not be forwarded (hop-by-hop)
_HOP_BY_HOP = frozenset([
    "connection", "keep-alive", "te", "trailers",
    "transfer-encoding", "upgrade",
    "proxy-authorization", "proxy-authenticate",
])


def _get_authenticated_container(user_id: str, token: Optional[str]) -> Optional[Container]:
    """Return the container only if the token matches the user_id's container api_token."""
    if not token:
        return None
    with get_db() as db:
        rec = (
            db.query(Container)
            .filter_by(user_id=user_id, api_token=token)
            .first()
        )
        if rec:
            db.expunge(rec)
        return rec


def _forward_headers(request: Request) -> dict:
    return {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
    }


# ── HTTP proxy ────────────────────────────────────────────────────────────────

@router.api_route(
    "/u/{user_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_http(user_id: str, path: str, request: Request):
    """Forward HTTP requests to the user's container."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    container = _get_authenticated_container(user_id, token)
    if not container:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if container.status not in ("running", "starting"):
        raise HTTPException(status_code=503, detail="Container not available")

    query = request.url.query
    target = f"http://{container.container_name}:8000/{path.lstrip('/')}"
    if query:
        target += f"?{query}"

    headers = _forward_headers(request)
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method=request.method,
                url=target,
                headers=headers,
                content=body,
            )

        resp_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in _HOP_BY_HOP
        }
        return StreamingResponse(
            iter([resp.content]),
            status_code=resp.status_code,
            headers=resp_headers,
        )
    except httpx.ConnectError:
        logger.warning(f"Container unreachable: /u/{user_id}/{path}")
        raise HTTPException(status_code=503, detail="Container unreachable")
    except Exception as e:
        logger.error(f"Proxy error /u/{user_id}/{path}: {e}")
        raise HTTPException(status_code=502, detail="Proxy error")


# ── WebSocket proxy ───────────────────────────────────────────────────────────

@router.websocket("/u/{user_id}/ws")
async def proxy_websocket(
    user_id: str,
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
):
    """Bridge WebSocket connections to the user's container."""
    await websocket.accept()

    container = _get_authenticated_container(user_id, token)
    if not container:
        await websocket.close(1008, "Unauthorized")
        return
    if container.status not in ("running", "starting"):
        await websocket.close(1013, "Container not available")
        return

    target_uri = f"ws://{container.container_name}:8000/ws"

    try:
        import websockets as ws_lib

        async with ws_lib.connect(target_uri, close_timeout=5) as upstream:
            async def client_to_upstream():
                try:
                    async for msg in websocket.iter_text():
                        await upstream.send(msg)
                except (WebSocketDisconnect, Exception):
                    pass

            async def upstream_to_client():
                try:
                    async for msg in upstream:
                        await websocket.send_text(str(msg))
                except Exception:
                    pass

            tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            # Await cancelled tasks to suppress CancelledError
            await asyncio.gather(*pending, return_exceptions=True)

    except Exception as e:
        logger.warning(f"WebSocket proxy error /u/{user_id}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
