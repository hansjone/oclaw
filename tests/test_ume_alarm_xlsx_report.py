from __future__ import annotations

from runtime.tools.experts.network_ops.ume_alarm_xlsx_report import (
    _filter_preset_items,
    _rows_from_aggregate_buckets,
    _rows_from_list_items,
    ume_alarm_xlsx_report_tool,
)
from runtime.tools.public.write_xlsx_tool import write_xlsx_tool
from svc.files.attachment_assets import AttachmentAssetStore


def test_write_xlsx_deliverable_flag(tmp_path, monkeypatch) -> None:
    store = AttachmentAssetStore(root_dir=tmp_path / "att")
    monkeypatch.setattr(
        "runtime.tools.public.write_xlsx_tool.AttachmentAssetStore",
        lambda root_dir=None: store if root_dir is None else AttachmentAssetStore(root_dir=root_dir),
    )
    out = write_xlsx_tool().handler(
        {
            "headers": ["a"],
            "rows": [[1]],
            "deliverable": True,
            "name": "d.xlsx",
        }
    )
    assert out.get("ok") is True
    assert out.get("deliverable") is True


def test_ume_alarm_xlsx_report_list_mocked(tmp_path, monkeypatch) -> None:
    store = AttachmentAssetStore(root_dir=tmp_path / "att")
    monkeypatch.setattr(
        "runtime.tools.public.write_xlsx_tool.AttachmentAssetStore",
        lambda root_dir=None: store if root_dir is None else AttachmentAssetStore(root_dir=root_dir),
    )

    def fake_http(method, path, *, params=None):
        assert path == "/v1/ume/alarms/raw"
        return {
            "ok": True,
            "data": {
                "total": 2,
                "items": [
                    {
                        "alarm_host_name": "NE-A",
                        "alarm_perceived_severity": "critical",
                        "alarm_event_type": "LOS",
                        "alarm_native_probable_cause": "fiber cut",
                        "alarm_object_name": "port-1",
                        "alarm_last_seen_at": "2026-08-01T00:00:00Z",
                        "alarm_is_cleared": "false",
                        "ne_ip_address": "10.0.0.1",
                    },
                    {
                        "alarm_host_name": "NE-B",
                        "alarm_perceived_severity": "major",
                        "alarm_event_type": "other",
                        "alarm_native_probable_cause": "fan",
                        "alarm_object_name": "fan-1",
                        "alarm_last_seen_at": "2026-08-01T01:00:00Z",
                        "alarm_is_cleared": "false",
                        "ne_ip_address": "10.0.0.2",
                    },
                ],
            },
        }

    monkeypatch.setattr(
        "runtime.tools.experts.network_ops.ume_alarm_xlsx_report.nt._http_json",
        fake_http,
    )
    out = ume_alarm_xlsx_report_tool().handler({"mode": "fiber_cut", "page_size": 50})
    assert out.get("ok") is True
    assert out.get("deliverable") is True
    assert out.get("row_count") == 1
    assert out.get("attachment_id")
    assert out["summary"]["mode"] == "fiber_cut"


def test_ume_alarm_xlsx_report_aggregate_mocked(tmp_path, monkeypatch) -> None:
    store = AttachmentAssetStore(root_dir=tmp_path / "att")
    monkeypatch.setattr(
        "runtime.tools.public.write_xlsx_tool.AttachmentAssetStore",
        lambda root_dir=None: store if root_dir is None else AttachmentAssetStore(root_dir=root_dir),
    )

    def fake_http(method, path, *, params=None):
        assert path == "/v1/ume/alarms/aggregate/raw"
        return {
            "ok": True,
            "data": {
                "total": 10,
                "group_by": "alarm_host_name",
                "by_ne_missing": 1,
                "buckets": [{"key": "NE-A", "count": 7}, {"key": "NE-B", "count": 3}],
            },
        }

    monkeypatch.setattr(
        "runtime.tools.experts.network_ops.ume_alarm_xlsx_report.nt._http_json",
        fake_http,
    )
    out = ume_alarm_xlsx_report_tool().handler(
        {"mode": "aggregate_by_host", "severity": "critical", "deliverable": False}
    )
    assert out.get("ok") is True
    assert out.get("deliverable") is False
    assert out.get("row_count") == 2


def test_filter_preset_and_row_helpers() -> None:
    items = [
        {"alarm_event_type": "Communication LOS", "alarm_host_name": "A"},
        {"alarm_event_type": "fan fail", "alarm_host_name": "B"},
    ]
    filtered = _filter_preset_items("fiber_cut", items)
    assert len(filtered) == 1
    headers, rows = _rows_from_list_items(filtered)
    assert headers[0] == "host_name"
    assert rows[0][0] == "A"
    _, agg_rows, meta = _rows_from_aggregate_buckets(
        {"buckets": [{"key": "H1", "count": 2}], "total": 2, "by_ne_missing": 0}
    )
    assert agg_rows == [["H1", 2]]
    assert meta["total"] == 2


def test_ume_alarm_xlsx_report_registered_when_builtin_disabled(monkeypatch) -> None:
    from runtime.tools import expert_registry

    monkeypatch.delenv("OCLAW_NETX_BUILTIN_TOOLS", raising=False)
    expert_registry.clear_expert_tool_cache()
    factories = expert_registry.discover_expert_tool_factories()
    names = {f().name for f in (factories.get("network_ops") or [])}
    assert "ume_alarm_xlsx_report" in names
    assert not any(n.startswith("netx_") for n in names)
    expert_registry.clear_expert_tool_cache()
