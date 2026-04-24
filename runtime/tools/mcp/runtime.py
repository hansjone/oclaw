from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpProcessRuntime:
    command: list[str]
    timeout_s: float = 30.0
    env_allowlist: list[str] | None = None
    _proc: subprocess.Popen[str] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _initialized: bool = False
    _request_id: int = 0

    @staticmethod
    def _build_runtime_env(env_allowlist: list[str] | None) -> dict[str, str] | None:
        if env_allowlist is None:
            return None
        keep_keys = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "SYSTEMDRIVE"}
        env: dict[str, str] = {}
        for k in keep_keys:
            if k in os.environ:
                env[k] = os.environ[k]
        for k in env_allowlist:
            key = str(k or "").strip()
            if key and key in os.environ:
                env[key] = os.environ[key]
        return env

    @staticmethod
    def _resolve_command(executable: str, env: dict[str, str] | None) -> str:
        cmd = str(executable or "").strip()
        if not cmd:
            return cmd
        if os.path.isabs(cmd) or os.path.sep in cmd or (os.path.altsep and os.path.altsep in cmd):
            return cmd
        resolved = shutil.which(cmd, path=(env or os.environ).get("PATH"))
        if resolved:
            return resolved
        if os.name == "nt":
            for suffix in (".cmd", ".exe", ".bat"):
                alt = shutil.which(cmd + suffix, path=(env or os.environ).get("PATH"))
                if alt:
                    return alt
        return cmd

    def start(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        env = self._build_runtime_env(self.env_allowlist)
        cmd = list(self.command or [])
        if cmd:
            cmd[0] = self._resolve_command(str(cmd[0]), env)
        popen_kwargs: dict[str, Any] = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True, "encoding": "utf-8", "env": env}
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            popen_kwargs["startupinfo"] = startupinfo
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self._proc = subprocess.Popen(cmd, **popen_kwargs)
        self._initialized = False
        self._request_id = 0

    def stop(self) -> None:
        p = self._proc
        if not p:
            return
        try:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
                try:
                    p.wait(timeout=2)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
        finally:
            for fp in (p.stdin, p.stdout, p.stderr):
                try:
                    if fp:
                        fp.close()
                except Exception:
                    pass
        self._proc = None
        self._initialized = False
        self._request_id = 0

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_with_retry(payload=payload, retries=0)

    def health(self) -> dict[str, Any]:
        res = self._request_jsonrpc("tools/list", {})
        if not bool(res.get("ok")):
            return res
        tools = self._normalize_tools(res.get("result"))
        return {"ok": True, "status": "ok", "tools_count": len(tools)}

    def tools_list(self) -> dict[str, Any]:
        res = self._request_jsonrpc("tools/list", {})
        if not bool(res.get("ok")):
            return res
        return {"ok": True, "tools": self._normalize_tools(res.get("result"))}

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments if isinstance(arguments, dict) else {}
        res = self._request_jsonrpc("tools/call", {"name": str(tool_name or ""), "arguments": args})
        if not bool(res.get("ok")):
            return res
        return self._normalize_tool_call_result(res.get("result"))

    def request_with_retry(self, payload: dict[str, Any], *, retries: int = 1) -> dict[str, Any]:
        tries = max(0, int(retries)) + 1
        last: dict[str, Any] = {"ok": False, "error_code": "mcp_runtime_failed", "error": "unknown"}
        for i in range(tries):
            self.start()
            ex = ThreadPoolExecutor(max_workers=1)
            fut = ex.submit(self._dispatch_request, payload)
            try:
                res = fut.result(timeout=max(0.1, float(self.timeout_s or 30.0)))
            except FuturesTimeoutError:
                try:
                    fut.cancel()
                except Exception:
                    pass
                self.stop()
                last = {"ok": False, "error_code": "mcp_runtime_timeout", "error": "request_timeout"}
                ex.shutdown(wait=False, cancel_futures=True)
                continue
            except Exception as exc:
                self.stop()
                last = {"ok": False, "error_code": "mcp_runtime_request_failed", "error": f"{type(exc).__name__}: {exc}"}
                ex.shutdown(wait=False, cancel_futures=True)
                continue
            else:
                ex.shutdown(wait=False, cancel_futures=True)
            if bool(res.get("ok")):
                return res
            last = res
            if i + 1 < tries:
                self.stop()
        return last

    def _dispatch_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        op = str((payload or {}).get("op") or "").strip().lower()
        if op:
            res = self._dispatch_op_jsonrpc(payload)
            if bool(res.get("ok")):
                return res
            if str(res.get("error_code") or "").startswith("mcp_runtime_"):
                try:
                    return self._exchange_legacy(payload)
                except Exception:
                    return res
            return res
        method = str((payload or {}).get("method") or "").strip()
        if method:
            params = (payload or {}).get("params")
            return self._request_jsonrpc(method, params if isinstance(params, dict) else {})
        return self._exchange_legacy(payload)

    def _request_jsonrpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.start()
        with self._lock:
            return self._jsonrpc_call_locked(method=method, params=params, skip_init=False)

    def _jsonrpc_call_locked(self, *, method: str, params: dict[str, Any], skip_init: bool) -> dict[str, Any]:
        if not skip_init and not self._initialized:
            init_res = self._jsonrpc_call_locked(
                method="initialize",
                params={"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ops-assistant", "version": "0.1.0"}},
                skip_init=True,
            )
            if not bool(init_res.get("ok")):
                return init_res
            self._jsonrpc_notify_locked("notifications/initialized", {})
            self._initialized = True
        p = self._proc
        if p is None or p.stdin is None or p.stdout is None:
            return {"ok": False, "error_code": "mcp_runtime_not_started", "error": "process_not_started"}
        self._request_id += 1
        rid = self._request_id
        req = {"jsonrpc": "2.0", "id": rid, "method": str(method), "params": params or {}}
        p.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        p.stdin.flush()
        while True:
            line = p.stdout.readline()
            if not line:
                return {"ok": False, "error_code": "mcp_runtime_empty_response", "error": "empty_response"}
            try:
                obj = json.loads(line)
            except Exception as exc:
                return {"ok": False, "error_code": "mcp_runtime_bad_json", "error": str(exc)}
            if not isinstance(obj, dict):
                return {"ok": False, "error_code": "mcp_runtime_invalid_payload", "error": "response_not_object"}
            if "jsonrpc" not in obj and "id" not in obj:
                return {"ok": False, "error_code": "mcp_runtime_protocol_mismatch", "error": "non_jsonrpc_response"}
            if obj.get("id") != rid:
                continue
            if isinstance(obj.get("error"), dict):
                err = obj.get("error") if isinstance(obj.get("error"), dict) else {}
                code = int(err.get("code") or 0)
                msg = str(err.get("message") or "jsonrpc_error")
                return {"ok": False, "error_code": f"mcp_rpc_error_{code}", "error": msg, "rpc_error": err}
            return {"ok": True, "result": obj.get("result"), "raw": obj}

    def _jsonrpc_notify_locked(self, method: str, params: dict[str, Any]) -> None:
        p = self._proc
        if p is None or p.stdin is None:
            return
        req = {"jsonrpc": "2.0", "method": str(method), "params": params or {}}
        p.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        p.stdin.flush()

    @staticmethod
    def _normalize_tools(result: Any) -> list[dict[str, Any]]:
        row = result if isinstance(result, dict) else {}
        items = row.get("tools") if isinstance(row.get("tools"), list) else []
        out: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or it.get("tool_name") or "").strip()
            if not name:
                continue
            params = it.get("inputSchema")
            if not isinstance(params, dict):
                params = it.get("parameters")
            out.append({"tool_name": name, "description": str(it.get("description") or ""), "parameters": params if isinstance(params, dict) else {}})
        return out

    @staticmethod
    def _normalize_tool_call_result(result: Any) -> dict[str, Any]:
        row = result if isinstance(result, dict) else {"raw": result}
        if bool(row.get("isError")):
            content = row.get("content") if isinstance(row.get("content"), list) else []
            text = ""
            for it in content:
                if isinstance(it, dict) and str(it.get("type") or "") == "text":
                    text = str(it.get("text") or "").strip()
                    if text:
                        break
            return {"ok": False, "error_code": "mcp_tool_call_failed", "error": text or "mcp_tool_call_failed", "result": row}
        return {"ok": True, "result": row, "data": row}

    def _dispatch_op_jsonrpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        op = str((payload or {}).get("op") or "").strip().lower()
        if op == "tools/list":
            return self.tools_list()
        if op == "health":
            return self.health()
        if op == "call_tool":
            tool_name = str((payload or {}).get("tool_name") or "").strip()
            args = (payload or {}).get("arguments")
            return self.call_tool(tool_name=tool_name, arguments=args if isinstance(args, dict) else {})
        return {"ok": False, "error_code": "mcp_runtime_unsupported_op", "error": f"unsupported_op:{op}"}

    def _exchange_legacy(self, payload: dict[str, Any]) -> dict[str, Any]:
        p = self._proc
        if p is None or p.stdin is None or p.stdout is None:
            return {"ok": False, "error_code": "mcp_runtime_not_started", "error": "process_not_started"}
        req = json.dumps(payload, ensure_ascii=False) + "\n"
        with self._lock:
            p.stdin.write(req)
            p.stdin.flush()
            line = p.stdout.readline()
        if not line:
            return {"ok": False, "error_code": "mcp_runtime_empty_response", "error": "empty_response"}
        try:
            obj = json.loads(line)
        except Exception as exc:
            return {"ok": False, "error_code": "mcp_runtime_bad_json", "error": str(exc)}
        if not isinstance(obj, dict):
            return {"ok": False, "error_code": "mcp_runtime_invalid_payload", "error": "response_not_object"}
        return obj
