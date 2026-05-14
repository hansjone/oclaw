# Assistant 库：SQLite → PostgreSQL

环境变量与字段说明见 [`ENVIRONMENT_VARIABLES.md`](./ENVIRONMENT_VARIABLES.md)。下文只列 **仓库根** 下各场景 **一条命令**（壳脚本；底层 migrator 由壳调用，不必手抄）。

---

**在目标 PostgreSQL 上建空表（schema，二选一）**

```bash
cd /path/to/oclaw && export PYTHONPATH=. && alembic upgrade head
```

（若不用 Alembic：用 `psql` 等对目标库执行一次 `svc/persistence/ddl/postgresql_bootstrap.sql`，**勿**又对同一库再跑一遍 Alembic。）

---

**Windows：备份 SQLite → 预演 → 导入 PG**（`_local\system.env` 里已配好 `AIA_ASSISTANT_DATABASE_URL` 等）

```powershell
cd D:\path\to\oclaw; .\runtime\operations\scripts\cutover_sqlite_to_postgresql.ps1 -LoadSystemEnv
```

---

**Linux / macOS：同上**

```bash
cd /path/to/oclaw && chmod +x runtime/operations/scripts/cutover_sqlite_to_postgresql.sh && ./runtime/operations/scripts/cutover_sqlite_to_postgresql.sh
```

---

**Linux / macOS：只要导入、不要割接备份流程**

```bash
cd /path/to/oclaw && chmod +x runtime/operations/scripts/assistant_import_sqlite_to_postgresql.sh && ./runtime/operations/scripts/assistant_import_sqlite_to_postgresql.sh --dry-run
```

确认后去掉 `--dry-run` 再执行同一条。

---

**导入完成后切到 PG 跑网关**

设置 `AIA_ASSISTANT_DB_BACKEND=postgresql` 与 `AIA_ASSISTANT_DATABASE_URL`（与导入目标一致），**重启**网关及所有连库的 worker。

---

**仅清空 PG 里会话数据（危险，确认库名）**

```powershell
# Windows：见脚本说明
.\runtime\operations\scripts\clear_postgres_chat_sessions.ps1
```

```bash
# 或仓库根（须设 AIA_CONFIRM_CHAT_SESSION_WIPE=1，见脚本）
export PYTHONPATH=. && python runtime/operations/scripts/clear_all_chat_sessions.py --yes --postgresql
```

排障与超时等见 `ENVIRONMENT_VARIABLES.md`。
