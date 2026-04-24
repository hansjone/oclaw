from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
import queue
import threading
from collections import deque
from pathlib import Path
from typing import Any

from oclaw.application.gateway import process_inbound_payload_usecase
from oclaw.channels.wecom.normalize import normalize_wecom_event, normalize_wecom_event_batch
from oclaw.platform.config.paths import db_path
from oclaw.platform.integrations.wecom_client import WeComClient
from oclaw.platform.persistence.sqlite_store import SqliteStore


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=True, default=str)
    except Exception:
        return str(obj)


def _account_id_from_payload(payload: dict[str, Any], store: SqliteStore) -> str:
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    for key in ("aibotid", "bot_id", "account_id"):
        v = meta.get(key)
        if v:
            return str(v).strip()
    for key in ("aibotid", "bot_id", "account_id"):
        v = payload.get(key)
        if v:
            return str(v).strip()
    raw = payload.get("raw")
    if isinstance(raw, dict):
        for key in ("aibotid", "bot_id", "account_id"):
            v = raw.get(key)
            if v:
                return str(v).strip()
    return str(store.get_setting("wecom_bot_id") or "").strip()


def _sanitize_outbound_text(text: str, *, max_chars: int = 1800) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    # Decode escaped newlines so WeCom shows real line breaks.
    s = s.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\N", "\n")
    # Remove hidden reasoning block before delivering to end users.
    lower = s.lower()
    start_tag = "<redacted_thinking>"
    end_tag = "</redacted_thinking>"
    if start_tag in lower and end_tag in lower:
        start = lower.find(start_tag)
        end = lower.find(end_tag, start)
        if end >= 0:
            s = (s[:start] + s[end + len(end_tag) :]).strip()
    if s.startswith(start_tag):
        s = s[len(start_tag) :].strip()
    # Collapse excessive blank lines for better mobile display.
    while "\n\n\n" in s:
        s = s.replace("\n\n\n", "\n\n")
    if len(s) > max_chars:
        s = s[:max_chars].rstrip() + "\n\n(回复过长，已截断)"
    return s


class _SingleInstanceLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.fh: Any | None = None

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.lock_path, "a+b")
        self.fh.seek(0)
        try:
            if os.name == "nt":
                import msvcrt  # type: ignore

                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl  # type: ignore

                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as exc:
            raise RuntimeError(f"wecom_longconn_already_running: {self.lock_path}") from exc

    def release(self) -> None:
        if self.fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt  # type: ignore

                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl  # type: ignore

                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self.fh.close()
        except Exception:
            pass
        self.fh = None


def _http_get_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    obj = json.loads(raw or "{}")
    return obj if isinstance(obj, dict) else {}


def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"content-type": "application/json", "accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {"ok": True, "raw": raw}
    return obj if isinstance(obj, dict) else {"ok": True, "raw": raw}


def _retry_count() -> int:
    raw = str(os.getenv("WECOM_LONGCONN_SEND_RETRY") or "2").strip()
    return max(1, min(int(raw) if raw.isdigit() else 2, 5))


def _load_mock_events() -> list[dict[str, Any]]:
    seed = str(os.getenv("WECOM_LONGCONN_MOCK_TEXT") or "帮助").strip()
    return [
        {
            "user_id": "u_mock_001",
            "chat_id": "u_mock_001",
            "text": seed,
            "is_group": False,
            "msgid": f"mock-{int(time.time())}",
        }
    ]


def _load_events_once(mode: str) -> list[dict[str, Any]]:
    if mode == "mock":
        return _load_mock_events()
    if mode == "pull":
        url = str(os.getenv("WECOM_LONGCONN_PULL_URL") or "").strip()
        if not url:
            raise RuntimeError("missing WECOM_LONGCONN_PULL_URL when mode=pull")
        obj = _http_get_json(url)
        return normalize_wecom_event_batch(obj)
    raise RuntimeError(f"unsupported WECOM_LONGCONN_MODE: {mode}")


def _run_ws_forever(*, sender: WeComClient, deliver_outbound: bool, use_response_url: bool) -> int:
    try:
        import websocket  # type: ignore
    except Exception as exc:
        raise RuntimeError("websocket-client not installed; run: pip install websocket-client") from exc
    bot_id, bot_secret = sender.get_bot_credentials()
    ws_url = str(os.getenv("WECOM_LONGCONN_WS_URL") or "wss://openws.work.weixin.qq.com").strip()
    seen_ids: deque[str] = deque(maxlen=2000)
    seen_set: set[str] = set()
    print(f"[wecom-longconn] websocket connecting url={ws_url} bot={bot_id}")
    store = sender.store
    workers_raw = (
        str(store.get_setting("AIA_WECOM_LONGCONN_WORKERS") or "").strip()
        or str(store.get_setting("WECOM_LONGCONN_WORKERS") or "").strip()
        or str(os.getenv("AIA_WECOM_LONGCONN_WORKERS") or "").strip()
        or str(os.getenv("WECOM_LONGCONN_WORKERS") or "").strip()
    )
    workers = 2
    if workers_raw.isdigit():
        workers = max(1, min(int(workers_raw), 8))
    in_max_raw = (
        str(store.get_setting("AIA_WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE") or "").strip()
        or str(store.get_setting("WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE") or "").strip()
        or str(os.getenv("AIA_WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE") or "").strip()
        or str(os.getenv("WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE") or "").strip()
    )
    in_q_max = 200
    if in_max_raw.isdigit():
        in_q_max = max(20, min(int(in_max_raw), 5000))
    inbound_q: "queue.Queue[tuple[dict[str, Any], dict[str, Any]]]" = queue.Queue(maxsize=in_q_max)
    outbound_q: "queue.Queue[dict[str, Any]]" = queue.Queue()
    ws_ref: dict[str, Any] = {"ws": None}
    stop_sender = threading.Event()

    def _drain_outbound_queue(*, ws: Any) -> None:
        while True:
            try:
                ob = outbound_q.get_nowait()
            except Exception:
                break
            try:
                if not deliver_outbound:
                    print("[wecom-longconn] outbound_skipped", _safe_json(ob))
                    continue
                text = str(ob.get("text") or "").strip()
                if not text:
                    continue
                response_url = str(ob.get("response_url") or "").strip()
                req_id = str(ob.get("callback_req_id") or uuid.uuid4().hex)
                rsp = {
                    "cmd": "aibot_respond_msg",
                    "headers": {"req_id": req_id},
                    "body": {"msgtype": "markdown", "markdown": {"content": text}},
                }
                sent = False
                if use_response_url and response_url:
                    try:
                        cb_payload = {"msgtype": "text", "text": {"content": text}}
                        cb_res: dict[str, Any] = {}
                        cb_err = -1
                        for _i in range(_retry_count()):
                            cb_res = _http_post_json(response_url, cb_payload, timeout=12)
                            cb_err = (
                                int(cb_res.get("errcode"))
                                if isinstance(cb_res, dict) and str(cb_res.get("errcode", "")).strip() != ""
                                else 0
                            )
                            if cb_err == 0:
                                break
                        if cb_err == 0:
                            sent = True
                            try:
                                store.set_setting("wecom_last_outbound_mode", "response_url")
                                store.set_setting("wecom_last_outbound_error", "")
                            except Exception:
                                pass
                            print("[wecom-longconn] outbound_sent_response_url", _safe_json({"url": response_url, "res": cb_res}))
                        else:
                            try:
                                store.set_setting(
                                    "wecom_last_outbound_error",
                                    f"response_url_errcode={cb_err}: {json.dumps(cb_res, ensure_ascii=False)}",
                                )
                            except Exception:
                                pass
                            print(
                                "[wecom-longconn] response_url_send_not_ok_fallback_ws",
                                _safe_json({"url": response_url, "res": cb_res}),
                            )
                    except Exception as exc:
                        try:
                            store.set_setting("wecom_last_outbound_error", f"response_url:{type(exc).__name__}: {exc}")
                        except Exception:
                            pass
                        print(f"[wecom-longconn] response_url_send_error: {type(exc).__name__}: {exc}")
                if not sent:
                    ws_ok = False
                    ws_err = ""
                    for _i in range(_retry_count()):
                        try:
                            ws.send(json.dumps(rsp, ensure_ascii=False))
                            ws_ok = True
                            ws_err = ""
                            break
                        except Exception as exc:
                            ws_err = f"{type(exc).__name__}: {exc}"
                            time.sleep(0.15)
                    if ws_ok:
                        try:
                            store.set_setting("wecom_last_outbound_mode", "ws")
                            store.set_setting("wecom_last_outbound_error", "")
                        except Exception:
                            pass
                        print("[wecom-longconn] outbound_sent_ws", _safe_json(rsp))
                    else:
                        try:
                            store.set_setting("wecom_last_outbound_error", f"ws_send_failed:{ws_err}")
                        except Exception:
                            pass
            finally:
                try:
                    outbound_q.task_done()
                except Exception:
                    pass

    def _sender_loop() -> None:
        while not stop_sender.is_set():
            try:
                # Block briefly to react immediately after worker enqueues replies.
                ob = outbound_q.get(timeout=0.3)
            except queue.Empty:
                continue
            except Exception:
                continue
            try:
                ws_obj = ws_ref.get("ws")
                if ws_obj is None:
                    # websocket reconnecting; put back and retry soon.
                    outbound_q.put(ob)
                    time.sleep(0.2)
                    continue
                if not deliver_outbound:
                    print("[wecom-longconn] outbound_skipped", _safe_json(ob))
                    continue
                text = str(ob.get("text") or "").strip()
                if not text:
                    continue
                response_url = str(ob.get("response_url") or "").strip()
                req_id = str(ob.get("callback_req_id") or uuid.uuid4().hex)
                rsp = {
                    "cmd": "aibot_respond_msg",
                    "headers": {"req_id": req_id},
                    "body": {"msgtype": "markdown", "markdown": {"content": text}},
                }
                sent = False
                if use_response_url and response_url:
                    try:
                        cb_payload = {"msgtype": "text", "text": {"content": text}}
                        cb_res: dict[str, Any] = {}
                        cb_err = -1
                        for _i in range(_retry_count()):
                            cb_res = _http_post_json(response_url, cb_payload, timeout=12)
                            cb_err = (
                                int(cb_res.get("errcode"))
                                if isinstance(cb_res, dict) and str(cb_res.get("errcode", "")).strip() != ""
                                else 0
                            )
                            if cb_err == 0:
                                break
                        if cb_err == 0:
                            sent = True
                            try:
                                store.set_setting("wecom_last_outbound_mode", "response_url")
                                store.set_setting("wecom_last_outbound_error", "")
                            except Exception:
                                pass
                            print("[wecom-longconn] outbound_sent_response_url", _safe_json({"url": response_url, "res": cb_res}))
                        else:
                            try:
                                store.set_setting(
                                    "wecom_last_outbound_error",
                                    f"response_url_errcode={cb_err}: {json.dumps(cb_res, ensure_ascii=False)}",
                                )
                            except Exception:
                                pass
                            print("[wecom-longconn] response_url_send_not_ok_fallback_ws", _safe_json({"url": response_url, "res": cb_res}))
                    except Exception as exc:
                        try:
                            store.set_setting("wecom_last_outbound_error", f"response_url:{type(exc).__name__}: {exc}")
                        except Exception:
                            pass
                        print(f"[wecom-longconn] response_url_send_error: {type(exc).__name__}: {exc}")
                if not sent:
                    ws_ok = False
                    ws_err = ""
                    for _i in range(_retry_count()):
                        try:
                            ws_obj.send(json.dumps(rsp, ensure_ascii=False))
                            ws_ok = True
                            ws_err = ""
                            break
                        except Exception as exc:
                            ws_err = f"{type(exc).__name__}: {exc}"
                            time.sleep(0.15)
                    if ws_ok:
                        try:
                            store.set_setting("wecom_last_outbound_mode", "ws")
                            store.set_setting("wecom_last_outbound_error", "")
                        except Exception:
                            pass
                        print("[wecom-longconn] outbound_sent_ws", _safe_json(rsp))
                    else:
                        try:
                            store.set_setting("wecom_last_outbound_error", f"ws_send_failed:{ws_err}")
                        except Exception:
                            pass
            finally:
                try:
                    outbound_q.task_done()
                except Exception:
                    pass

    def _worker_loop(idx: int) -> None:
        while True:
            payload, meta2 = inbound_q.get()
            try:
                out = process_inbound_payload_usecase(payload)
                replies = out.get("replies") if isinstance(out, dict) else []
                if not isinstance(replies, list):
                    replies = []
                for rep in replies:
                    if not isinstance(rep, dict):
                        continue
                    text = str(rep.get("text") or "").strip()
                    text = _sanitize_outbound_text(text)
                    if not text:
                        continue
                    outbound_q.put(
                        {
                            "callback_req_id": str(meta2.get("callback_req_id") or ""),
                            "response_url": str(meta2.get("response_url") or ""),
                            "text": text,
                            "raw_rep": rep,
                        }
                    )
            except Exception as exc:
                outbound_q.put(
                    {
                        "callback_req_id": str(meta2.get("callback_req_id") or ""),
                        "response_url": str(meta2.get("response_url") or ""),
                        "text": f"[wecom-longconn] worker_error: {type(exc).__name__}: {exc}",
                        "raw_rep": {},
                    }
                )
            finally:
                inbound_q.task_done()

    for i in range(workers):
        threading.Thread(target=_worker_loop, args=(i,), name=f"wecom_worker_{i}", daemon=True).start()
    threading.Thread(target=_sender_loop, name="wecom_sender", daemon=True).start()

    while True:
        ws = None
        try:
            ws = websocket.create_connection(ws_url, timeout=30)
            ws.settimeout(60)
            ws_ref["ws"] = ws
            sub = {
                "cmd": "aibot_subscribe",
                "headers": {"req_id": uuid.uuid4().hex},
                "body": {"bot_id": bot_id, "secret": bot_secret},
            }
            ws.send(json.dumps(sub, ensure_ascii=False))
            print("[wecom-longconn] subscribe sent")
            while True:
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    # Idle timeout is expected when no inbound message arrives.
                    # Keep the connection alive instead of reconnecting.
                    try:
                        ws.ping()
                        print("[wecom-longconn] ping")
                    except Exception:
                        raise
                    # Drain outbound queue on idle ticks so replies are pushed immediately,
                    # not delayed until the next inbound message.
                    _drain_outbound_queue(ws=ws)
                    continue
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    print("[wecom-longconn] non_json_message", raw)
                    continue
                if not isinstance(msg, dict):
                    continue
                cmd = str(msg.get("cmd") or "").strip()
                if not cmd:
                    body0 = msg.get("body") if isinstance(msg.get("body"), dict) else {}
                    cmd = str(body0.get("cmd") or body0.get("type") or msg.get("type") or "").strip()
                if not cmd and "errcode" in msg and "errmsg" in msg:
                    ack_req_id = ""
                    h = msg.get("headers")
                    if isinstance(h, dict):
                        ack_req_id = str(h.get("req_id") or "").strip()
                    ack_err = int(msg.get("errcode") or 0)
                    ack_msg = str(msg.get("errmsg") or "").strip()
                    try:
                        store.set_setting("wecom_last_ack_req_id", ack_req_id)
                        store.set_setting("wecom_last_ack_errcode", str(ack_err))
                        store.set_setting("wecom_last_ack_errmsg", ack_msg)
                        if ack_err == 0:
                            store.set_setting("wecom_last_outbound_error", "")
                        else:
                            store.set_setting("wecom_last_outbound_error", f"ack_errcode={ack_err}: {ack_msg}")
                    except Exception:
                        pass
                    print("[wecom-longconn] outbound_ack", _safe_json(msg))
                    continue
                try:
                    store.set_setting("wecom_last_cmd", cmd)
                except Exception:
                    pass
                if cmd == "aibot_subscribe_rsp":
                    print("[wecom-longconn] subscribe_rsp", json.dumps(msg, ensure_ascii=False))
                    continue
                if cmd not in ("aibot_msg_callback", "aibot_event_callback"):
                    try:
                        store.set_setting(
                            "wecom_last_unknown_cmd_payload",
                            json.dumps(msg, ensure_ascii=False, default=str)[:4000],
                        )
                    except Exception:
                        pass
                    print(
                        "[wecom-longconn] unknown_cmd",
                        _safe_json(
                            {"cmd": cmd, "keys": sorted(msg.keys())[:20]},
                        ),
                    )
                    continue
                body = msg.get("body") if isinstance(msg.get("body"), dict) else {}
                headers = msg.get("headers") if isinstance(msg.get("headers"), dict) else {}
                callback_req_id = str(headers.get("req_id") or "").strip()
                try:
                    store.set_setting(
                        "wecom_last_raw_body",
                        json.dumps(body, ensure_ascii=False, default=str)[:4000],
                    )
                    from_obj = body.get("from")
                    from_uid = ""
                    if isinstance(from_obj, dict):
                        from_uid = str(from_obj.get("userid") or from_obj.get("user_id") or from_obj.get("id") or "").strip()
                    elif isinstance(from_obj, str):
                        from_uid = from_obj.strip()
                    if from_uid:
                        store.set_setting("wecom_last_raw_from_user", from_uid)
                except Exception:
                    pass
                if cmd == "aibot_event_callback":
                    event_type = str(body.get("event") or body.get("event_type") or body.get("type") or "").strip()
                    event_obj = body.get("event") if isinstance(body.get("event"), dict) else {}
                    event_type_norm = str(
                        event_obj.get("eventtype")
                        or event_obj.get("type")
                        or event_type
                    ).strip()
                    from_obj = body.get("from")
                    from_user = ""
                    if isinstance(from_obj, dict):
                        from_user = str(
                            from_obj.get("userid")
                            or from_obj.get("user_id")
                            or from_obj.get("id")
                            or from_obj.get("from_user_id")
                            or ""
                        ).strip()
                    elif isinstance(from_obj, str):
                        from_user = from_obj.strip()
                    print(
                        "[wecom-longconn] event_callback",
                        _safe_json(
                            {
                                "event_type": event_type_norm or event_type,
                                "from_user": from_user,
                                "keys": sorted(body.keys())[:20],
                            },
                        ),
                    )
                    if (event_type_norm or event_type).lower() == "disconnected_event":
                        try:
                            store.set_setting("wecom_last_parse_error", "disconnected_event")
                        except Exception:
                            pass
                    continue
                try:
                    payload = normalize_wecom_event(body)
                except Exception as exc:
                    print(
                        "[wecom-longconn] skip_invalid_msg_callback",
                        _safe_json(
                            {
                                "error": f"{type(exc).__name__}: {exc}",
                                "keys": sorted(body.keys())[:30],
                            },
                        ),
                    )
                    try:
                        store.set_setting("wecom_last_parse_error", f"{type(exc).__name__}: {exc}")
                    except Exception:
                        pass
                    continue
                try:
                    store.set_setting(
                        "wecom_last_normalized_payload",
                        json.dumps(payload, ensure_ascii=False, default=str)[:4000],
                    )
                except Exception:
                    pass
                msgid = str(body.get("msgid") or payload.get("metadata", {}).get("msgid") or "").strip()
                if msgid and msgid in seen_set:
                    continue
                if msgid:
                    if len(seen_ids) >= seen_ids.maxlen and seen_ids:
                        old = seen_ids.popleft()
                        seen_set.discard(old)
                    seen_ids.append(msgid)
                    seen_set.add(msgid)
                try:
                    now = str(int(time.time()))
                    user_id = str(payload.get("user_id") or "").strip()
                    store.set_setting("wecom_last_msg_ts", now)
                    if user_id:
                        store.set_setting("wecom_last_from_user", user_id)
                    raw_recent = str(store.get_setting("wecom_recent_from_users") or "[]")
                    recent = json.loads(raw_recent)
                    if not isinstance(recent, list):
                        recent = []
                    recent = [x for x in recent if isinstance(x, dict)]
                    if user_id:
                        recent = [x for x in recent if str(x.get("user_id") or "") != user_id]
                        recent.insert(0, {"user_id": user_id, "ts": now})
                    store.set_setting("wecom_recent_from_users", json.dumps(recent[:20], ensure_ascii=False))
                except Exception:
                    pass
                try:
                    inbound_q.put_nowait(
                        (
                            payload,
                            {
                                "callback_req_id": callback_req_id or uuid.uuid4().hex,
                                "response_url": str(body.get("response_url") or "").strip(),
                            },
                        )
                    )
                except Exception:
                    # Inbound backlog; drop gracefully to keep the websocket loop healthy.
                    try:
                        store.set_setting("wecom_last_outbound_error", "inbound_queue_full")
                    except Exception:
                        pass

                # Drain outbound queue opportunistically.
                _drain_outbound_queue(ws=ws)
        except KeyboardInterrupt:
            print("[wecom-longconn] stopped by user")
            return 0
        except Exception as exc:
            print(f"[wecom-longconn] ws_loop_error: {type(exc).__name__}: {exc}")
            time.sleep(3)
        finally:
            ws_ref["ws"] = None
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass


def run_forever() -> int:
    store = SqliteStore(db_path())
    sender = WeComClient(store)
    lock = _SingleInstanceLock(Path(db_path()).resolve().parent / "locks" / "wecom_longconn.lock")
    lock.acquire()
    default_mode = "ws"
    mode = str(os.getenv("WECOM_LONGCONN_MODE") or default_mode).strip().lower()
    interval_s = max(1.0, float(os.getenv("WECOM_LONGCONN_INTERVAL_SEC") or "3"))
    deliver_outbound = str(os.getenv("WECOM_LONGCONN_DELIVER_OUTBOUND") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    seen_ids: deque[str] = deque(maxlen=2000)
    seen_set: set[str] = set()

    # Prefer response_url by default for lower latency and better delivery semantics.
    use_response_url = str(os.getenv("WECOM_LONGCONN_USE_RESPONSE_URL") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    print(
        f"[wecom-longconn] started mode={mode} interval={interval_s}s outbound={deliver_outbound} use_response_url={use_response_url}"
    )
    try:
        if mode == "ws":
            return _run_ws_forever(
                sender=sender,
                deliver_outbound=deliver_outbound,
                use_response_url=use_response_url,
            )
        while True:
            try:
                events = _load_events_once(mode)
                if not events:
                    time.sleep(interval_s)
                    continue
                for evt in events:
                    payload = normalize_wecom_event(evt)
                    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
                    msgid = str(meta.get("msgid") or "").strip()
                    if msgid and msgid in seen_set:
                        continue
                    if msgid:
                        if len(seen_ids) >= seen_ids.maxlen and seen_ids:
                            old = seen_ids.popleft()
                            seen_set.discard(old)
                        seen_ids.append(msgid)
                        seen_set.add(msgid)
                    out = process_inbound_payload_usecase(payload)
                    replies = out.get("replies") if isinstance(out, dict) else []
                    if not isinstance(replies, list):
                        replies = []
                    for rep in replies:
                        if not isinstance(rep, dict):
                            continue
                        if not deliver_outbound:
                            print("[wecom-longconn] outbound_skipped", _safe_json(rep))
                            continue
                        to_user = str(payload.get("user_id") or "").strip()
                        text = str(rep.get("text") or "").strip()
                        text = _sanitize_outbound_text(text)
                        if not to_user or not text:
                            continue
                        aid = _account_id_from_payload(payload, store)
                        print(
                            "[wecom-longconn] outbound_skipped_http_removed use_ws_mode",
                            _safe_json({"to_user": to_user, "account_id": aid or "", "text_len": len(text)}),
                        )
            except KeyboardInterrupt:
                print("[wecom-longconn] stopped by user")
                return 0
            except Exception as exc:
                print(f"[wecom-longconn] loop_error: {type(exc).__name__}: {exc}")
                time.sleep(interval_s)
    finally:
        lock.release()


def main() -> int:
    return run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
