from __future__ import annotations

import json
from pathlib import Path


def _iter_jsonl(path: Path):
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        try:
            yield i, json.loads(s)
        except Exception as e:
            raise SystemExit(f"{path}: invalid json at line {i}: {e}") from e


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data" / "eval"
    if not data_dir.exists():
        print("offline_eval: no data/eval directory, skip")
        return 0
    files = sorted(p for p in data_dir.glob("*.jsonl"))
    if not files:
        print("offline_eval: no eval jsonl files, skip")
        return 0
    total = 0
    for fp in files:
        for line_no, obj in _iter_jsonl(fp):
            total += 1
            if not isinstance(obj, dict):
                raise SystemExit(f"{fp}:{line_no}: expected object")
            if not str(obj.get("id") or "").strip():
                raise SystemExit(f"{fp}:{line_no}: missing id")
            # Optional lightweight schema checks used by repo's eval fixtures.
            for k in ("assert_contains", "assert_not_contains"):
                if k in obj and not isinstance(obj.get(k), list):
                    raise SystemExit(f"{fp}:{line_no}: {k} must be a list")
    print(f"offline_eval: ok files={len(files)} cases={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

