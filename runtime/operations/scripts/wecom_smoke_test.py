from __future__ import annotations

import json
import sys
import uuid

from svc.config.paths import db_path
from svc.integrations.wecom_client import WeComClient
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import get_assistant_store


def main() -> int:
    store = get_assistant_store()
    client = WeComClient(store)
    try:
        bot_id, _bot_secret = client.get_bot_credentials()
    except Exception as exc:
        print("ok=0")
        print("step=read_bot_config")
        print(f"error={type(exc).__name__}: {exc}")
        return 1
    print("ok=1")
    print("mode=bot_api")
    print(f"bot_id={bot_id}")
    if "--ws" not in sys.argv[1:]:
        print("ws_skipped=1")
        print("hint=use --ws for subscribe handshake test")
        return 0
    try:
        import websocket  # type: ignore
    except Exception:
        print("ok=0")
        print("step=import_websocket_client")
        print("error=websocket-client not installed, run: pip install websocket-client")
        return 1
    try:
        ws = websocket.create_connection("wss://openws.work.weixin.qq.com", timeout=15)
        ws.send(
            json.dumps(
                {
                    "cmd": "aibot_subscribe",
                    "headers": {"req_id": uuid.uuid4().hex},
                    "body": {"bot_id": bot_id, "secret": client.get_bot_credentials()[1]},
                },
                ensure_ascii=False,
            )
        )
        raw = ws.recv()
        ws.close()
        print("ws_subscribe_response=" + str(raw))
        return 0
    except Exception as exc:
        print("ok=0")
        print("step=ws_subscribe")
        print(f"error={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
