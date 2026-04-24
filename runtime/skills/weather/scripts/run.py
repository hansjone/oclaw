from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request


def _read_stdin_json() -> dict:
    try:
        raw = input()
    except EOFError:
        raw = ""
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def main() -> None:
    # Windows default console encoding may be GBK; force UTF-8 so symbols like ☀ do not crash.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    payload = _read_stdin_json()
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    location = str(args.get("location") or "Shanghai").strip() or "Shanghai"
    fmt = str(args.get("format") or "3").strip() or "3"
    # wttr.in: GET /<location>?format=<fmt>
    loc_q = urllib.parse.quote(location, safe="")
    url = f"https://wttr.in/{loc_q}?format={urllib.parse.quote(fmt, safe='')}"
    req = urllib.request.Request(url, headers={"User-Agent": "oclaw-skill-weather/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8", errors="ignore").strip()
        out = {"ok": True, "location": location, "format": fmt, "text": text}
    except Exception as exc:
        out = {"ok": False, "error_code": "fetch_failed", "error": f"{type(exc).__name__}:{exc}"}
    output = json.dumps(out, ensure_ascii=False)
    try:
        print(output)
    except UnicodeEncodeError:
        # Last-resort fallback for environments where stdout reconfigure is unavailable.
        sys.stdout.buffer.write((output + "\n").encode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()

