from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {module_name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _mount_whatsapp_module():
    root = Path(__file__).resolve().parents[1] / "runtime" / "extensions" / "whatsapp"
    pkg_root = types.ModuleType("ocxw")
    pkg_root.__path__ = [str(root.parent)]
    sys.modules["ocxw"] = pkg_root
    pkg = types.ModuleType("ocxw.whatsapp")
    pkg.__path__ = [str(root)]
    sys.modules["ocxw.whatsapp"] = pkg
    return _load_module("ocxw.whatsapp.api", root / "api.py")


def test_whatsapp_target_predicates() -> None:
    api = _mount_whatsapp_module()
    assert api.is_whatsapp_group_jid("12345@g.us") is True
    assert api.is_whatsapp_group_jid("12345@s.whatsapp.net") is False

    assert api.is_whatsapp_user_target("13800138000") is True
    assert api.is_whatsapp_user_target("+8613800138000") is True
    assert api.is_whatsapp_user_target("13800138000@s.whatsapp.net") is True
    assert api.is_whatsapp_user_target("bad_target") is False

    assert api.looks_like_whatsapp_target_id("12345@g.us") is True
    assert api.looks_like_whatsapp_target_id("13800138000") is True
    assert api.looks_like_whatsapp_target_id("not-a-target") is False


def test_whatsapp_target_normalization() -> None:
    api = _mount_whatsapp_module()
    assert api.normalize_whatsapp_target("12345@g.us") == "12345@g.us"
    assert api.normalize_whatsapp_target("+86 138-0013-8000") == "8613800138000@s.whatsapp.net"
    assert api.normalize_whatsapp_target("13800138000@s.whatsapp.net") == "13800138000@s.whatsapp.net"

    try:
        api.normalize_whatsapp_target("")
    except ValueError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty target")


def test_whatsapp_allow_from_entries_normalize_and_deduplicate() -> None:
    api = _mount_whatsapp_module()
    out = api.normalize_whatsapp_allow_from_entries(
        ["+86 13800138000", "13800138000@s.whatsapp.net", "12345@g.us", "bad@@@", "12345@g.us"]
    )
    assert out == ("12345@g.us", "13800138000@s.whatsapp.net", "8613800138000@s.whatsapp.net")

