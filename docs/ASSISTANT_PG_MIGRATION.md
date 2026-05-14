# Assistant 库：SQLite → PostgreSQL 迁移指南

本文说明如何将 **助手主持久化**（会话、`chat_message`、设置、租户等）从默认 **SQLite** 迁到 **PostgreSQL**，以及割接前后的操作顺序与排障要点。实现上仍通过同一套 `SqliteStore` API；仅底层连接与 SQL 方言不同。

更完整的环境变量说明见 [`ENVIRONMENT_VARIABLES.md`](./ENVIRONMENT_VARIABLES.md) 中的「存储与迁移」一节；本文侧重 **操作步骤与脚本**。

---

## 1. 何时需要读本文

- 生产或预发要把 **assistant 主库** 从 `data/ai_ops.sqlite`（或自定义 SQLite 路径）迁到 **PostgreSQL**。
- 需要 **一次性导入历史数据**，再切换 `AIA_ASSISTANT_DB_BACKEND=postgresql` 上线。
- 排查「PG 上表空 / 导入失败 / 网关连错库」等问题。

若只做 **新部署、无历史 SQLite 数据**：在空库上建 schema 后，直接配置 PG 与 `postgresql` 后端即可，**不必**跑数据导入脚本。

---

## 2. 核心概念

| 项目 | 说明 |
|------|------|
| 后端选择 | `AIA_ASSISTANT_DB_BACKEND`：`sqlite`（默认）或 `postgresql`（别名 `pg` / `postgres` 等）。 |
| PG 连接串 | `AIA_ASSISTANT_DATABASE_URL`（或 `OPS_ASSISTANT_DATABASE_URL` / `AIA_ASSISTANT_PG_DSN` 等别名）。SQLAlchemy 使用时会规范为 `postgresql+psycopg://…`。 |
| Schema 来源 | 推荐 **`alembic upgrade head`**（`alembic.ini` 的 `script_location = assistant_migrations`）。等价方式：在目标库执行 `svc/persistence/ddl/postgresql_bootstrap.sql`（与迁移首版语义一致，二选一即可，勿混用导致重复建表报错）。 |
| 数据导入 | `runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py`：**只拷数据**，不建表；要求目标 PG **已存在 schema**。默认要求 PG 中待拷贝表 **为空**（可用 `--allow-non-empty` 跳过检查，自担重复/FK 风险）。 |
| 网关 | 进程内通过 `get_assistant_store()` 单例连库；**切换 URL 或后端后需重启网关**（必要时 `reset` 相关进程环境）。 |

---

## 3. 推荐总体顺序（ checklist ）

1. **在 PostgreSQL 上创建数据库**（例如 `oclaw`），为应用用户授予 `CREATE` / `USAGE` on schema `public` 及后续表所需权限。
2. 在**目标库**上完成 **schema**：`alembic upgrade head`（仓库根执行，且已配置指向该库的 `DATABASE_URL` / 环境变量），或执行 `postgresql_bootstrap.sql`。
3. **不要**在未建表的空库上直接启动依赖全表的生产网关（会报错或产生不一致状态）。应完成第 2 步后再启动，或先保持 `sqlite` 仅跑导入机。
4. 使用下文 **割接脚本** 或 **直接调用 migrator**：先做 **`--dry-run`**，确认行数与表列表无误后再实导。
5. 将运行环境改为 **`AIA_ASSISTANT_DB_BACKEND=postgresql`** 并设置 **`AIA_ASSISTANT_DATABASE_URL`**（与导入时**同一**目标库）。
6. **重启**网关及所有使用 `get_assistant_store()` 的 worker，使新配置生效。
7. 验证管理台会话列表、发一条测试消息、必要时跑 `AIA_TEST_PG_URL` 相关测试（见下文）。

---

## 4. Schema：Alembic（推荐）

仓库根：

```bash
# 已设置 AIA_ASSISTANT_DATABASE_URL 指向目标 PG，且已安装依赖（含 alembic、psycopg）
cd /path/to/oclaw
export PYTHONPATH=.
alembic upgrade head
```

首版迁移 `assistant_migrations/versions/001_assistant_pg_initial.py` 会读取 `svc/persistence/ddl/postgresql_bootstrap.sql` 并逐条执行（仅当方言为 `postgresql` 时）。

**说明**：`downgrade()` 未实现；回滚依赖 **数据库备份 / 文件备份**，而非 Alembic 反向迁移。

---

## 5. 数据导入：`migrate_assistant_sqlite_to_postgresql.py`

路径：`runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py`。

**行为摘要**

- 从 SQLite 读表顺序（按 `PRAGMA foreign_key_list` 拓扑），仅插入 **SQLite 与 PG `public` 中同名的共有列**。
- 默认若任一待拷贝表在 PG 中 **已有行** 则 **退出**（避免重复）；`--allow-non-empty` 可关闭该检查。
- `--dry-run`：只统计源表行数，**不写 PG**。

**常用参数**

| 参数 | 含义 |
|------|------|
| `--sqlite PATH` | 源 SQLite 文件路径。 |
| `--sqlite-from-db-path` | 使用 `db_path()`（受 `AIA_ASSISTANT_DB_PATH` 等影响）作为源库。 |
| `--load-system-env` | 合并 `_local/system.env`（与网关 `load_system_env` 思路一致，便于设备上只维护一份 env）。 |
| `--pg-url URL` | 目标 PG；不设则从环境变量读取（见脚本 `--help`）。 |
| `--dry-run` | 预演。 |
| `--allow-non-empty` | 允许目标表非空（慎用）。 |
| `--batch N` | 批量插入行数，默认 500。 |

**示例（本机预演）**

```bash
cd /path/to/oclaw
export PYTHONPATH=.
export AIA_ASSISTANT_DATABASE_URL='postgresql+psycopg://USER:PASS@127.0.0.1:5432/oclaw'
python runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py \
  --load-system-env --sqlite-from-db-path --dry-run
# 确认无报错后去掉 --dry-run 再执行
```

**显式路径示例**

```bash
python runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py \
  --sqlite data/ai_ops.sqlite \
  --pg-url 'postgresql+psycopg://postgres:pass@127.0.0.1:5432/oclaw'
```

---

## 6. 割接包装脚本（备份 + dry-run + 导入）

在跑正式导入前，**强烈建议**备份 SQLite 文件。脚本会把副本放到 `data/pg_cutover_backups/`（可改参数或环境变量）。

### 6.1 Windows（PowerShell）

`runtime/operations/scripts/cutover_sqlite_to_postgresql.ps1`

典型用法：

```powershell
cd D:\path\to\oclaw
# 若 URL 写在 _local\system.env 中：
.\runtime\operations\scripts\cutover_sqlite_to_postgresql.ps1 -LoadSystemEnv
# 或显式传入：
.\runtime\operations\scripts\cutover_sqlite_to_postgresql.ps1 -PgUrl "postgresql+psycopg://..."
```

常用开关：`-SqlitePath`、`-BackupDir`、`-SkipDryRun`、`-DryRunOnly`、`-NoBackup`（不推荐生产）、`-LoadSystemEnv`。

### 6.2 Linux / bash

`runtime/operations/scripts/cutover_sqlite_to_postgresql.sh`

- 环境变量：`SQLITE_PATH`、`BACKUP_DIR`、`NO_BACKUP`、`SKIP_DRY_RUN`、`DRY_RUN_ONLY` 等（见脚本头部注释）。
- 默认会 `--load-system-env` 并解析 SQLite 路径。

仅 **导入**（不复制备份逻辑时也可用轻量包装）：

`runtime/operations/scripts/assistant_import_sqlite_to_postgresql.sh`（内部调用 migrator 的 `--load-system-env --sqlite-from-db-path`）。

---

## 7. 切换运行时与网关

导入完成后：

1. 设置 **`AIA_ASSISTANT_DB_BACKEND=postgresql`**。
2. 设置 **`AIA_ASSISTANT_DATABASE_URL`**（与导入目标一致）。
3. 重启 **网关**、**wiki worker**、**渠道 worker** 等所有持有 DB 连接的进程。

**注意**：`get_assistant_store()` 在进程内会按 `(backend, 连接键)` 缓存；改环境后必须重启进程，否则会连旧库。

---

## 8. 验证与自动化测试

- 管理台：会话列表、打开历史会话、发送一条新消息，确认读写正常。
- 单测：设置环境变量 **`AIA_TEST_PG_URL`** 后，部分用例会对真实 PG 跑冒烟（例如 `tests/test_database_backend.py`）。详见 [`ENVIRONMENT_VARIABLES.md`](./ENVIRONMENT_VARIABLES.md) 中 `AIA_TEST_PG_URL` 说明。

---

## 9. 备份与回滚

- **割接脚本** 默认将 SQLite 复制到 `data/pg_cutover_backups/<原名>_pre_pg_<时间戳>.sqlite`。
- 若导入后需回退到 SQLite：恢复该备份文件为 `data/ai_ops.sqlite`（或你的 `AIA_ASSISTANT_DB_PATH`），将 `AIA_ASSISTANT_DB_BACKEND` 改回 `sqlite` 或未设置，重启服务。
- PostgreSQL 侧回滚：依赖实例级备份（快照 / `pg_dump`），不在应用脚本内自动完成。

---

## 10. 仅清空 PG 中的对话数据（可选）

若要在 **PostgreSQL** 上删除所有会话及相关行（危险操作），使用：

- `runtime/operations/scripts/clear_postgres_chat_sessions.ps1`（加载 `_local/system.env`、强制 PG、设置确认变量后调用 Python），或  
- `python runtime/operations/scripts/clear_all_chat_sessions.py --yes --postgresql`  
  且必须同时设置 **`AIA_CONFIRM_CHAT_SESSION_WIPE=1`**。

详见脚本内说明；**勿**在未确认库名时针对生产执行。

---

## 11. 常见问题（排障）

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 导入报「表非空」 | PG 已有数据 | 换新库或 `--allow-non-empty`（谨慎） |
| 网关仍像连 SQLite | 环境未生效 / 未重启 | 检查进程环境、`assistant_store` 单例 |
| `invalid_credentials` / 连接失败 | URL 或网络或权限 | 用 `psql` 或 `psycopg` 单独测连 |
| 部分表未拷贝 | PG 无同名表 | 先 `alembic upgrade head`；查看 migrator 打印的 `skip (not in PG public schema)` |
| Windows 上 Alembic 编码问题 | 控制台代码页 | 使用 UTF-8 终端或重定向日志到文件 |

---

## 12. 相关文件索引

| 路径 | 用途 |
|------|------|
| `alembic.ini` | Alembic 配置，`script_location = assistant_migrations` |
| `assistant_migrations/` | PG schema 版本链 |
| `svc/persistence/ddl/postgresql_bootstrap.sql` | 初始 DDL（与首版迁移同源） |
| `svc/config/database.py` | 后端与 DSN 解析 |
| `svc/persistence/assistant_store.py` | `get_assistant_store()` 工厂 |
| `runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py` | 数据导入 |
| `runtime/operations/scripts/cutover_sqlite_to_postgresql.ps1` / `.sh` | 备份 + 预演 + 导入 |
| `runtime/operations/scripts/clear_all_chat_sessions.py` | 清空会话（需确认 env） |
| `docs/ENVIRONMENT_VARIABLES.md` | 环境变量权威列表 |

---

**维护建议**：若变更割接流程或新增迁移步骤，请同步更新本文与 `ENVIRONMENT_VARIABLES.md` 中的摘要，避免文档分叉。
