from __future__ import annotations

import hashlib
from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.types import StandardMessage
from oclaw.runtime.worker import _maybe_generate_title_on_third_round


class _DummyResp:
    def __init__(self, content: str) -> None:
        self.content = content


class _DummyModel:
    def __init__(self, content: str = "第三轮标题") -> None:
        self._content = content

    def chat(self, _messages, _tools, on_token=None):  # noqa: ANN001
        return _DummyResp(self._content)


def test_worker_third_round_title_generation_updates_stage3(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "worker-title.sqlite"))
    tenant = store.create_tenant("Team")
    user = store.create_user_account(
        tenant_id=str(tenant["id"]),
        username="tester",
        display_name="Tester",
        role="owner",
        password_hash=hashlib.sha256("test-pass".encode("utf-8")).hexdigest(),
        is_active=True,
    )
    session = store.create_session_for_user(
        title="第一轮标题",
        tenant_id=str(tenant["id"]),
        user_id=str(user["id"]),
    )
    sid = str(session.id)
    store.set_setting(f"AIA_SESSION_AUTO_TITLE_STAGE:{sid}", "1")
    store.add_message(session_id=sid, role="user", content="第一轮问题")
    store.add_message(session_id=sid, role="assistant", content="第一轮回答")
    store.add_message(session_id=sid, role="user", content="第二轮问题")
    store.add_message(session_id=sid, role="assistant", content="第二轮回答")

    msg = StandardMessage(
        session_id=sid,
        tenant_id=str(tenant["id"]),
        user_id=str(user["id"]),
        role="member",
        channel="admin_chat",
        text="第三轮问题",
        attachments=[],
        metadata={"lang": "zh"},
    )
    _maybe_generate_title_on_third_round(store=store, msg=msg, model=_DummyModel())

    renamed = store.get_session(sid)
    assert renamed is not None
    assert str(getattr(renamed, "title", "") or "") == "第三轮标题"
    assert str(store.get_setting(f"AIA_SESSION_AUTO_TITLE_STAGE:{sid}") or "") == "3"


def test_worker_third_round_rejects_prose_title_uses_fallback(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "worker-title-fb.sqlite"))
    tenant = store.create_tenant("Team")
    user = store.create_user_account(
        tenant_id=str(tenant["id"]),
        username="tester",
        display_name="Tester",
        role="owner",
        password_hash=hashlib.sha256("test-pass".encode("utf-8")).hexdigest(),
        is_active=True,
    )
    session = store.create_session_for_user(
        title="第一轮标题",
        tenant_id=str(tenant["id"]),
        user_id=str(user["id"]),
    )
    sid = str(session.id)
    store.set_setting(f"AIA_SESSION_AUTO_TITLE_STAGE:{sid}", "1")
    store.add_message(session_id=sid, role="user", content="第一轮问题")
    store.add_message(session_id=sid, role="assistant", content="第一轮回答")
    store.add_message(session_id=sid, role="user", content="第二轮问题")
    store.add_message(session_id=sid, role="assistant", content="第二轮回答")

    msg = StandardMessage(
        session_id=sid,
        tenant_id=str(tenant["id"]),
        user_id=str(user["id"]),
        role="member",
        channel="admin_chat",
        text="第三轮问题",
        attachments=[],
        metadata={"lang": "zh"},
    )
    garbage = "您好！我是 Claude Code，一个软件工程助手。" + "x" * 80
    _maybe_generate_title_on_third_round(store=store, msg=msg, model=_DummyModel(content=garbage))

    renamed = store.get_session(sid)
    assert renamed is not None
    assert str(getattr(renamed, "title", "") or "") == "第一轮问题"
    assert str(store.get_setting(f"AIA_SESSION_AUTO_TITLE_STAGE:{sid}") or "") == "3"
