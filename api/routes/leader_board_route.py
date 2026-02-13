from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

from core.utils.leaderboard.service import build_leaderboard
from core.utils.leaderboard.websocket import manager
from core.utils.permissions import websocket_authenticate

api_router = APIRouter(prefix="/leaderboard")

@api_router.websocket("/ws")
async def leaderboard_ws(ws: WebSocket):
    try:
        current_user = await websocket_authenticate(
            websocket=ws,
            allowed_roles=["user"],
        )

        # ws.state.user = current_user
        await manager.connect(ws)
        leaderboard = await build_leaderboard()
        await ws.send_json({
            "type": "leaderboard_init",
            "data": leaderboard
        })

        while True:
            await ws.receive_text()


    except WebSocketException as e:

        # 🔥 Send proper error message before closing

        await ws.send_json({

            "type": "error",

            "message": e.reason or "Authentication failed"

        })

        await ws.close(code=1008)


    except WebSocketDisconnect:

        manager.disconnect(ws)

    except Exception as e:
        await ws.send_json({
            "type": "error",
            "message": "Internal server error",
            "error": str(e)
        })
        await ws.close(code=1011)