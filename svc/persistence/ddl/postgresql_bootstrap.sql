-- Generated for PostgreSQL assistant store (from SQLite schema)
SET client_min_messages TO WARNING;
CREATE TABLE IF NOT EXISTS chat_session (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_message_at TEXT
                );

CREATE TABLE IF NOT EXISTS tenant (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS app_user (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    username TEXT,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, avatar_attachment_id TEXT,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS channel_identity (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS channel_identity_v2 (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, account_id, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS bind_code (
                    code TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    used_at TEXT,
                    used_by_external_user_id TEXT,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS channel_session (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    external_chat_id TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, external_chat_id, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS channel_session_v2 (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    external_chat_id TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, account_id, external_chat_id, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS user_channel_account (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    config TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id, channel, account_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS todo_item (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    assignee_user_id TEXT,
                    title TEXT NOT NULL,
                    due_at TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_user_id) REFERENCES app_user(id) ON DELETE CASCADE,
                    FOREIGN KEY(assignee_user_id) REFERENCES app_user(id) ON DELETE SET NULL
                );

CREATE TABLE IF NOT EXISTS chat_message (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    attachments TEXT,
                    turn_uuid TEXT,
                    event_type TEXT,
                    event_payload TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS ui_session_owner (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS user_workspace_path_allowlist (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    extra_roots TEXT NOT NULL DEFAULT '',
                    allow_any_path INTEGER NOT NULL DEFAULT 0,
                    allow_high_risk_public_tools INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS auth_session (
                    session_token_hash TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS role_permission (
                    role TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (role, permission)
                );

CREATE TABLE IF NOT EXISTS user_permission (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id, permission),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    actor_tenant_id TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS attachment_acl (
                    attachment_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (attachment_id, tenant_id, user_id, session_id, source),
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS tool_log (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    specialist TEXT NOT NULL DEFAULT '',
                    args TEXT NOT NULL,
                    result TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    duration_ms INTEGER,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS tool_plugin (
                    plugin_name TEXT NOT NULL,
                    plugin_version TEXT NOT NULL,
                    entry_point TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plugin_name, entry_point)
                );

CREATE TABLE IF NOT EXISTS mcp_server_registry (
                    server_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '',
                    entry_command TEXT NOT NULL DEFAULT '',
                    entry_args TEXT NOT NULL DEFAULT '[]',
                    env_schema TEXT NOT NULL DEFAULT '{}',
                    required_permissions TEXT NOT NULL DEFAULT '[]',
                    risk_level TEXT NOT NULL DEFAULT 'high',
                    timeout_s DOUBLE PRECISION NOT NULL DEFAULT 30,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS mcp_server_installation (
                    id BIGSERIAL PRIMARY KEY,
                    server_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_code TEXT NOT NULL DEFAULT '',
                    detail TEXT NOT NULL DEFAULT '{}',
                    install_command TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS mcp_server_health (
                    server_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '{}',
                    checked_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS mcp_server_tool (
                    server_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    parameters TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (server_id, tool_name)
                );

CREATE TABLE IF NOT EXISTS app_setting (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    is_secret INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS knowledge_chunk (
                    chunk_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS knowledge_embedding (
                    chunk_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chunk_id, model),
                    FOREIGN KEY(chunk_id) REFERENCES knowledge_chunk(chunk_id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS memory_item (
                    memory_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'memory',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                );

CREATE TABLE IF NOT EXISTS memory_vector (
                    memory_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (memory_id, model),
                    FOREIGN KEY(memory_id) REFERENCES memory_item(memory_id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS memory_hit_log (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    memory_id TEXT,
                    query_text TEXT NOT NULL,
                    score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'memory',
                    timestamp TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS oclaw_task (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    task_type TEXT NOT NULL DEFAULT 'async_turn',
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    result TEXT NOT NULL DEFAULT '{}',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    claimed_by TEXT,
                    lease_expires_at TEXT,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
                );

CREATE TABLE IF NOT EXISTS oclaw_run (
                    run_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS oclaw_attempt (
                    id BIGSERIAL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    attempt_no INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS agent_audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    specialist TEXT NOT NULL,
                    task_kind TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS agent_eval_log (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    specialist TEXT NOT NULL,
                    task_kind TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    cost_hint DOUBLE PRECISION NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS trace_event (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS llm_profile (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    model TEXT,
                    base_url TEXT,
                    api_key TEXT,
                    updated_at TEXT NOT NULL
                , is_builtin INTEGER NOT NULL DEFAULT 0, hide_in_ui INTEGER NOT NULL DEFAULT 0, owner_user_id TEXT, thinking_mode_enabled INTEGER NOT NULL DEFAULT 0, reasoning_effort TEXT);

CREATE TABLE IF NOT EXISTS llm_profile_user_grant (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by_user_id TEXT,
                    UNIQUE(tenant_id, profile_id, user_id),
                    FOREIGN KEY(profile_id) REFERENCES llm_profile(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );

CREATE TABLE IF NOT EXISTS llm_profile_tenant_grant (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by_user_id TEXT,
                    UNIQUE(tenant_id, profile_id),
                    FOREIGN KEY(profile_id) REFERENCES llm_profile(id) ON DELETE CASCADE
                );

CREATE INDEX IF NOT EXISTS idx_chat_session_activity ON chat_session(COALESCE(last_message_at, created_at) DESC, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_app_user_tenant_username ON app_user(tenant_id, username);

CREATE INDEX IF NOT EXISTS idx_user_channel_account_channel_account ON user_channel_account(channel, account_id, is_active);

CREATE INDEX IF NOT EXISTS idx_chat_message_session_turn_uuid ON chat_message(session_id, turn_uuid);

CREATE INDEX IF NOT EXISTS idx_ui_session_owner_tenant_user ON ui_session_owner(tenant_id, user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ui_session_owner_tenant_user_session ON ui_session_owner(tenant_id, user_id, session_id);

CREATE INDEX IF NOT EXISTS idx_ui_session_owner_tenant_session ON ui_session_owner(tenant_id, session_id);

CREATE INDEX IF NOT EXISTS idx_auth_session_user_expires ON auth_session(user_id, expires_at);

CREATE INDEX IF NOT EXISTS idx_admin_audit_actor_ts ON admin_audit_log(actor_user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_attachment_acl_tenant_attachment ON attachment_acl(tenant_id, attachment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_attachment_acl_user_attachment ON attachment_acl(tenant_id, user_id, attachment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_attachment_acl_session_attachment ON attachment_acl(session_id, attachment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_item_tenant_user_updated ON memory_item(tenant_id, user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_hit_log_tenant_user_ts ON memory_hit_log(tenant_id, user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_memory_item_session_updated ON memory_item(session_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_oclaw_task_status_updated ON oclaw_task(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_oclaw_task_tenant_session ON oclaw_task(tenant_id, session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_oclaw_run_tenant_session ON oclaw_run(tenant_id, session_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_oclaw_attempt_run_no ON oclaw_attempt(run_id, attempt_no);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_source_updated ON knowledge_chunk(source, updated_at);

CREATE INDEX IF NOT EXISTS idx_trace_event_session_id_id ON trace_event(session_id, id);

CREATE INDEX IF NOT EXISTS idx_llm_profile_grant_user ON llm_profile_user_grant(tenant_id, user_id);

CREATE INDEX IF NOT EXISTS idx_llm_profile_grant_profile ON llm_profile_user_grant(tenant_id, profile_id);

CREATE INDEX IF NOT EXISTS idx_llm_profile_tenant_grant ON llm_profile_tenant_grant(tenant_id, profile_id);

CREATE INDEX IF NOT EXISTS idx_chat_message_session_id_id ON chat_message(session_id, id);
