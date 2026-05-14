"""Copy assistant data from SQLite (db_path file) into PostgreSQL (schema from Alembic / bootstrap).

**Prerequisite:** target PostgreSQL already has schema (``alembic upgrade head`` or
``svc/persistence/ddl/postgresql_bootstrap.sql``). This script copies **data only**.

Tables are copied in **foreign-key safe order** (from SQLite ``PRAGMA foreign_key_list``), and only
**columns present in both** SQLite and PostgreSQL are inserted.

By default the script aborts if any target table in ``public`` already has rows (empty PG only).
Use ``--allow-non-empty`` to skip that check (you are responsible for avoiding duplicates / FK errors).

**PostgreSQL URL** is taken from ``--pg-url`` if set; otherwise from the first non-empty environment
variable among ``AIA_ASSISTANT_DATABASE_URL``, ``OPS_ASSISTANT_DATABASE_URL``, ``AIA_ASSISTANT_PG_DSN``,
``OPS_ASSISTANT_PG_DSN``. Use ``--load-system-env`` to merge ``_local/system.env`` first (same as the
HTTP gateway).

**Open-source / headless device (Linux example)**::

    export AIA_ASSISTANT_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/oclaw'
    export AIA_ASSISTANT_DB_PATH=/var/lib/oclaw/data/ai_ops.sqlite   # optional; default data/ai_ops.sqlite under repo
    cd /path/to/oclaw && PYTHONPATH=. python runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py \\
        --load-system-env --sqlite-from-db-path --dry-run
    # then same without --dry-run

Or use the wrapper script ``runtime/operations/scripts/assistant_import_sqlite_to_postgresql.sh``.

**Explicit paths**::

    python runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py \\
        --sqlite data/ai_ops.sqlite \\
        --pg-url postgresql+psycopg://postgres:pass@127.0.0.1:5432/oclaw

"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from svc.persistence.pg_adapter import normalize_psycopg_conninfo


def _pg_row_first_value(row: Any) -> Any:
    if row is None:
        raise ValueError("expected a row")
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\Z")


def _require_ident(name: str) -> str:
    if not _IDENT.fullmatch(name):
        raise ValueError(f"invalid SQL identifier: {name!r}")
    return name


def _sqlite_user_tables(sl: sqlite3.Connection) -> list[str]:
    rows = sl.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [str(r[0]) for r in rows]


def _pg_public_tables(pg: psycopg.Connection) -> set[str]:
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT tablename FROM pg_catalog.pg_tables
            WHERE schemaname = 'public'
            """
        )
        return {str(_pg_row_first_value(r)) for r in cur.fetchall()}


def _fk_parents_for_table(sl: sqlite3.Connection, table: str) -> set[str]:
    t = _require_ident(table)
    rows = sl.execute(f"PRAGMA foreign_key_list({t})").fetchall()
    out: set[str] = set()
    for r in rows:
        # (id, seq, table, from, to, on_update, on_delete, match)
        ref = str(r[2])
        if ref:
            out.add(ref)
    return out


def _topological_sort(nodes: list[str], parents: dict[str, set[str]]) -> list[str]:
    """``parents[t]`` = tables that must be copied *before* ``t`` (referenced by FK)."""
    node_set = list(nodes)
    seen = set(node_set)
    if len(seen) != len(node_set):
        raise ValueError("duplicate table in migration list")

    children: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {}
    for t in node_set:
        ps = parents.get(t, set()) & seen
        indegree[t] = len(ps)
        for p in ps:
            children[p].append(t)
    for ch in children.values():
        ch.sort()

    queue = sorted([t for t in node_set if indegree[t] == 0])
    out: list[str] = []
    while queue:
        n = queue.pop(0)
        out.append(n)
        for c in children[n]:
            indegree[c] -= 1
            if indegree[c] == 0:
                queue.append(c)
                queue.sort()
    if len(out) != len(seen):
        remain = seen - set(out)
        raise SystemExit(
            "Cannot derive a foreign-key-safe copy order (cycle or unresolved FK). "
            f"Remaining tables: {sorted(remain)}"
        )
    return out


def _migration_order(sl: sqlite3.Connection, tables: list[str]) -> list[str]:
    node_set = list(tables)
    parents = {t: _fk_parents_for_table(sl, t) & set(node_set) for t in node_set}
    return _topological_sort(node_set, parents)


def _sqlite_columns(sl: sqlite3.Connection, table: str) -> list[str]:
    t = _require_ident(table)
    rows = sl.execute(f"PRAGMA table_info({t})").fetchall()
    # cid, name, type, notnull, dflt_value, pk
    return [str(r[1]) for r in rows]


def _pg_columns(pg: psycopg.Connection, table: str) -> set[str]:
    t = _require_ident(table)
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (t,),
        )
        return {str(_pg_row_first_value(r)) for r in cur.fetchall()}


def _common_columns(sl: sqlite3.Connection, pg: psycopg.Connection, table: str) -> list[str]:
    sc = _sqlite_columns(sl, table)
    pc = _pg_columns(pg, table)
    return [c for c in sc if c in pc and _IDENT.fullmatch(c)]


def _assert_pg_tables_empty(pg: psycopg.Connection, tables: Iterable[str]) -> None:
    with pg.cursor() as cur:
        for t in sorted(set(tables)):
            _require_ident(t)
            cur.execute(f'SELECT COUNT(*) AS n FROM "{t}"')
            row = cur.fetchone()
            n = int(_pg_row_first_value(row))
            if n:
                raise SystemExit(
                    f"Refusing to import: PostgreSQL table {t!r} already has {n} row(s). "
                    "Use an empty schema after alembic upgrade, or pass --allow-non-empty if you "
                    "really intend to append (duplicates / FK failures are your risk)."
                )


def _sqlite_row_counts(sl: sqlite3.Connection, tables: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tables:
        _require_ident(t)
        n = int(sl.execute(f"SELECT COUNT(*) FROM {_require_ident(t)}").fetchone()[0])
        out[t] = n
    return out


def _pg_row_counts(pg: psycopg.Connection, tables: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    with pg.cursor() as cur:
        for t in tables:
            _require_ident(t)
            cur.execute(f'SELECT COUNT(*) AS n FROM "{t}"')
            row = cur.fetchone()
            out[t] = int(_pg_row_first_value(row))
    return out


def _copy_table(
    *,
    sl: sqlite3.Connection,
    pg: psycopg.Connection,
    table: str,
    cols: list[str],
    dry_run: bool,
    batch: int,
) -> int:
    if not cols:
        return 0
    t = _require_ident(table)
    cur = sl.execute(f"SELECT {', '.join(_require_ident(c) for c in cols)} FROM {t}")
    rows = cur.fetchall()
    if not rows:
        return 0
    if dry_run:
        return len(rows)
    col_sql = ", ".join(f'"{_require_ident(c)}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f'INSERT INTO "{t}" ({col_sql}) VALUES ({placeholders})'
    tuples = [tuple(r[c] for c in cols) for r in rows]
    with pg.cursor() as pc:
        for i in range(0, len(tuples), max(1, batch)):
            chunk = tuples[i : i + max(1, batch)]
            pc.executemany(sql, chunk)
    return len(rows)


def _serial_columns(pg: psycopg.Connection) -> list[tuple[str, str]]:
    """Tables/columns backed by a PostgreSQL sequence (BIGSERIAL etc.), for post-import setval."""
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_default IS NOT NULL
              AND column_default LIKE 'nextval%'
            ORDER BY table_name, column_name
            """
        )
        rows = cur.fetchall()
    out: list[tuple[str, str]] = []
    for r in rows:
        if isinstance(r, dict):
            t = str(r["table_name"])
            c = str(r["column_name"])
        else:
            t = str(r[0])
            c = str(r[1])
        if t and c:
            out.append((_require_ident(t), _require_ident(c)))
    return out


def _sync_sequences(pg: psycopg.Connection) -> None:
    for t, col in _serial_columns(pg):
        with pg.cursor() as cur:
            cur.execute(f'SELECT COALESCE(MAX("{col}"), 1) AS mx FROM "{t}"')
            row = cur.fetchone()
            mx = int(_pg_row_first_value(row))
            try:
                cur.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, %s), %s, true)",
                    (t, col, mx),
                )
            except Exception:
                pass


def _pg_url_from_environ() -> str:
    return (
        os.getenv("AIA_ASSISTANT_DATABASE_URL")
        or os.getenv("OPS_ASSISTANT_DATABASE_URL")
        or os.getenv("AIA_ASSISTANT_PG_DSN")
        or os.getenv("OPS_ASSISTANT_PG_DSN")
        or ""
    ).strip()


def _resolve_sqlite_path(arg: str | None, use_db_path: bool) -> Path:
    if use_db_path:
        from svc.config.paths import db_path

        return Path(db_path()).expanduser().resolve()
    if not arg:
        raise SystemExit("Either pass --sqlite PATH or --sqlite-from-db-path")
    return Path(arg).expanduser().resolve()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sqlite", default=None, help="Path to source SQLite assistant DB")
    ap.add_argument(
        "--sqlite-from-db-path",
        action="store_true",
        help="Use db_path() from env (AIA_ASSISTANT_DB_PATH / default) as SQLite source",
    )
    ap.add_argument(
        "--load-system-env",
        action="store_true",
        help="Merge _local/system.env into the process (for DB_PATH / DATABASE_URL on devices)",
    )
    ap.add_argument(
        "--pg-url",
        default=None,
        help="Target PostgreSQL URL; if omitted, use AIA_ASSISTANT_DATABASE_URL (or OPS_* / *_PG_DSN)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Count rows only; do not write to PG")
    ap.add_argument(
        "--allow-non-empty",
        action="store_true",
        help="Do not abort when target PG tables already contain rows",
    )
    ap.add_argument(
        "--batch",
        type=int,
        default=500,
        help="Rows per executemany batch (default 500)",
    )
    args = ap.parse_args()
    if bool(args.load_system_env):
        from svc.config.bootstrap_env import load_system_env

        load_system_env(force=True)

    sqlite_path = _resolve_sqlite_path(args.sqlite, bool(args.sqlite_from_db_path))
    if not sqlite_path.is_file():
        raise SystemExit(f"sqlite file not found: {sqlite_path}")

    raw_pg = (args.pg_url or "").strip() or _pg_url_from_environ()
    if not raw_pg:
        raise SystemExit(
            "No PostgreSQL URL: pass --pg-url or set one of "
            "AIA_ASSISTANT_DATABASE_URL, OPS_ASSISTANT_DATABASE_URL, "
            "AIA_ASSISTANT_PG_DSN, OPS_ASSISTANT_PG_DSN (use --load-system-env to read _local/system.env)."
        )
    pg_url = normalize_psycopg_conninfo(raw_pg)
    sl = sqlite3.connect(str(sqlite_path))
    sl.row_factory = sqlite3.Row
    try:
        sl.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    pg = psycopg.connect(pg_url, row_factory=dict_row, autocommit=False)
    try:
        sqlite_tables = _sqlite_user_tables(sl)
        pg_tables = _pg_public_tables(pg)
        common = [t for t in sqlite_tables if t in pg_tables]
        skipped_sqlite = [t for t in sqlite_tables if t not in pg_tables]
        if skipped_sqlite:
            print("skip (not in PG public schema):", ", ".join(skipped_sqlite))

        if not common:
            raise SystemExit("No common tables between SQLite and PostgreSQL; nothing to copy.")

        order = _migration_order(sl, common)
        if not args.dry_run and not args.allow_non_empty:
            _assert_pg_tables_empty(pg, common)

        src_counts = _sqlite_row_counts(sl, order)
        total = 0
        copied: list[str] = []
        for t in order:
            cols = _common_columns(sl, pg, t)
            if not cols:
                n0 = src_counts.get(t, 0)
                if n0 > 0:
                    print(f"{t}: SKIP (no common columns; sqlite has {n0} rows — schema drift)")
                continue
            n = _copy_table(sl=sl, pg=pg, table=t, cols=cols, dry_run=bool(args.dry_run), batch=int(args.batch))
            print(f"{t}: {n} rows ({len(cols)} columns)")
            total += n
            copied.append(t)
        if not args.dry_run:
            pg.commit()
            _sync_sequences(pg)
            pg.commit()
            verify = _pg_row_counts(pg, order)
            bad = [t for t in copied if verify.get(t, 0) != src_counts.get(t, 0)]
            if bad:
                print("WARNING: row count mismatch PG vs SQLite for:", ", ".join(bad))
                for t in bad:
                    print(f"  {t}: sqlite={src_counts.get(t, 0)} pg={verify.get(t, 0)}")
            else:
                print("verify: row counts match SQLite for all copied tables")
        print("total rows (copied or dry-run counted):", total)
    except BaseException:
        pg.rollback()
        raise
    finally:
        sl.close()
        pg.close()


if __name__ == "__main__":
    main()
