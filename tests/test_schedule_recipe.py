from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.scheduler.recipe import (
    compile_playbook_instruction,
    list_ops_recipe_templates,
    looks_like_complex_schedule_prompt,
    normalize_recipe,
    preview_markdown,
    prompt_summary_from_recipe,
    recipe_has_playbook,
    recipe_missing_fields,
    resolve_ops_recipe_template,
)
from runtime.scheduler.turn_text import build_scheduled_turn_instruction, scheduled_turn_system_suffix
from runtime.tools.experts.productivity.schedule_tools import (
    schedule_create_tool,
    schedule_propose_tool,
)
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class RecipeHelpersTests(unittest.TestCase):
    def test_normalize_and_missing_fields(self) -> None:
        recipe = normalize_recipe(
            {
                "goal": "发值班报告",
                "steps": ["拉数据"],
                "success_criteria": [],
            }
        )
        self.assertEqual(recipe["goal"], "发值班报告")
        self.assertEqual(recipe_missing_fields(recipe), ["steps", "success_criteria"])
        self.assertFalse(recipe_has_playbook(recipe))

    def test_playbook_ready(self) -> None:
        recipe = normalize_recipe(
            {
                "goal": "发值班报告",
                "steps": ["拉数据", "写摘要", "发群"],
                "success_criteria": ["群内收到 PDF"],
                "output": {"need_attachments": True},
            }
        )
        self.assertTrue(recipe_has_playbook(recipe))
        self.assertEqual(recipe_missing_fields(recipe), [])
        preview = preview_markdown(
            name="值班报告",
            schedule_kind="cron",
            schedule_expr="0 9 * * 1",
            timezone_name="Asia/Shanghai",
            recipe=recipe,
            lang="zh",
        )
        self.assertIn("拉数据", preview)
        self.assertIn("确认", preview)
        instr = compile_playbook_instruction(recipe=recipe, lang="zh")
        self.assertIn("定时工作流", instr)
        self.assertIn("save_deliverable_attachment", instr)
        self.assertEqual(prompt_summary_from_recipe(recipe), "发值班报告")

    def test_complex_prompt_heuristic(self) -> None:
        self.assertTrue(looks_like_complex_schedule_prompt("把刚才那件事做成每周一定时"))
        self.assertTrue(looks_like_complex_schedule_prompt("继续刚才那个生成 PDF 流程"))
        self.assertFalse(looks_like_complex_schedule_prompt("提醒喝水"))

    def test_ops_recipe_templates(self) -> None:
        items = list_ops_recipe_templates()
        ids = {str(x.get("id") or "") for x in items}
        self.assertIn("ume_alarm_tally_daily", ids)
        self.assertIn("ume_critical_xlsx_daily", ids)
        self.assertIn("ne_license_check_weekly", ids)
        self.assertIn("bandwidth_congestion_daily", ids)
        tmpl = resolve_ops_recipe_template("alarm_tally")
        assert tmpl is not None
        self.assertTrue(recipe_has_playbook(tmpl))
        self.assertEqual((tmpl.get("source") or {}).get("template_id"), "ume_alarm_tally_daily")
        cong = resolve_ops_recipe_template("congestion")
        assert cong is not None
        self.assertEqual((cong.get("source") or {}).get("template_id"), "bandwidth_congestion_daily")
        cong_blob = " ".join(str(s) for s in (cong.get("steps") or []) + (cong.get("constraints") or []))
        self.assertIn("ume_ne_ids", cong_blob)
        self.assertIn("batch", cong_blob.lower())
        license_tmpl = resolve_ops_recipe_template("license_check")
        assert license_tmpl is not None
        lic_blob = " ".join(str(s) for s in (license_tmpl.get("steps") or []))
        self.assertIn("ne_ids", lic_blob)
        self.assertIn("never one-NE", lic_blob)
        self.assertIsNone(resolve_ops_recipe_template("nope"))

    def test_compile_injects_batch_cli_constraint(self) -> None:
        recipe = {
            "goal": "CLI check top hosts",
            "steps": [
                "Pull congestion alarms",
                "Run execManagedNe show interface on top hosts",
            ],
            "success_criteria": ["Group gets summary"],
        }
        instr = compile_playbook_instruction(recipe=recipe, lang="en")
        self.assertIn("ne_ids", instr)
        self.assertIn("ume_ne_ids", instr)
        self.assertIn("batch", instr.lower())
        # Alarm-only playbook should not get CLI batch constraint.
        alarm_only = {
            "goal": "Alarm tally",
            "steps": ["aggregateUmeAlarms", "Summarize by_severity"],
            "success_criteria": ["Done"],
        }
        alarm_instr = compile_playbook_instruction(recipe=alarm_only, lang="en")
        self.assertNotIn("Multi-NE CLI default", alarm_instr)

    def test_turn_instruction_modes(self) -> None:
        reminder = build_scheduled_turn_instruction(prompt_text="喝水", mode="scheduled", lang="zh")
        self.assertIn("提醒意图", reminder)
        recipe = {
            "goal": "发报告",
            "steps": ["A", "B"],
            "success_criteria": ["完成"],
        }
        playbook = build_scheduled_turn_instruction(
            prompt_text="发报告",
            mode="scheduled",
            lang="zh",
            recipe=recipe,
        )
        self.assertIn("步骤", playbook)
        self.assertIn("A", playbook)
        self.assertIn("工作流", scheduled_turn_system_suffix(lang="zh", playbook=True))
        self.assertIn("提醒", scheduled_turn_system_suffix(lang="zh", playbook=False))

    def test_synthesize_step_headers_and_previous_run(self) -> None:
        from runtime.scheduler.recipe import synthesize_recipe_from_prompt
        from runtime.scheduler.turn_text import append_previous_run_context

        prompt = (
            'Run "unmanaged by dying gasp" report.\n\n'
            "CRITICAL — Follow this exact algorithm:\n\n"
            "Step 1 — Query BN EMS failures:\n"
            "- Query active alarms: native_probable_cause = \"BN EMS alarm NE communication failure\"\n\n"
            "Step 2 — Query Remote dying gasp:\n"
            "- Query active alarms: native_probable_cause LIKE \"%Remote dying gasp%\"\n\n"
            "Step 3 — Join and deliver XLSX via save_deliverable_attachment.\n"
        )
        recipe = synthesize_recipe_from_prompt(prompt)
        assert recipe is not None
        self.assertTrue(recipe_has_playbook(recipe))
        self.assertGreaterEqual(len(recipe["steps"]), 3)
        self.assertEqual((recipe.get("source") or {}).get("compiled_from"), "prompt_text")
        self.assertTrue((recipe.get("output") or {}).get("need_attachments"))
        instr = build_scheduled_turn_instruction(
            prompt_text=prompt,
            mode="scheduled",
            lang="en",
            recipe=recipe,
            previous_run={
                "status": "success",
                "finished_at": "2026-08-10T06:00:00+00:00",
                "reply_text": "Found 12 candidates; 3 confirmed.",
            },
        )
        self.assertIn("Scheduled playbook", instr)
        self.assertIn("Previous run context", instr)
        self.assertIn("Found 12 candidates", instr)
        with_prev = append_previous_run_context(
            "base",
            previous_run={"status": "failed", "error": "timeout on CLI"},
            lang="en",
        )
        self.assertIn("timeout on CLI", with_prev)


class ScheduleRecipeToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "recipe.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        reset_assistant_store_singleton()
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        user = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash="x",
            is_active=True,
        )
        self.user_id = str(user["id"])

    def tearDown(self) -> None:
        reset_assistant_store_singleton()
        self._tmp.cleanup()

    def test_propose_rejects_incomplete_recipe(self) -> None:
        out = schedule_propose_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "name": "报告",
                "schedule_kind": "cron",
                "schedule_expr": "0 9 * * 1",
                "recipe": {"goal": "发报告", "steps": ["一步"]},
            }
        )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "recipe_incomplete")

    def test_propose_and_create_playbook(self) -> None:
        recipe = {
            "goal": "每周发值班 PDF",
            "steps": ["拉取数据", "生成 PDF", "发群"],
            "success_criteria": ["群内收到 PDF"],
            "constraints": ["不改历史文件"],
            "output": {"need_attachments": True},
        }
        proposed = schedule_propose_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "session_id": "sess-1",
                "name": "值班报告",
                "schedule_kind": "cron",
                "schedule_expr": "0 9 * * 1",
                "recipe": recipe,
            }
        )
        self.assertTrue(proposed.get("ok"), proposed)
        self.assertTrue(proposed.get("draft"))
        self.assertIn("preview_markdown", proposed)

        created = schedule_create_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "session_id": "sess-1",
                "name": "值班报告",
                "prompt_text": "每周发值班 PDF",
                "schedule_kind": "cron",
                "schedule_expr": "0 9 * * 1",
                "recipe": recipe,
            }
        )
        self.assertTrue(created.get("ok"), created)
        job = created.get("job") or {}
        self.assertEqual((job.get("recipe") or {}).get("goal"), "每周发值班 PDF")
        self.assertEqual(len((job.get("recipe") or {}).get("steps") or []), 3)

        got = self.store.scheduled_job_get(job_id=str(job["id"]), tenant_id=self.tenant_id)
        assert got is not None
        self.assertIn("每周发值班 PDF", got.recipe_json)

    def test_create_rejects_vague_complex_prompt(self) -> None:
        out = schedule_create_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "name": "bad",
                "prompt_text": "继续刚才那个",
                "schedule_kind": "interval",
                "schedule_expr": "3600",
            }
        )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "recipe_required")

    def test_create_from_ops_recipe_template(self) -> None:
        out = schedule_create_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "name": "Daily tally",
                "recipe_template_id": "ume_alarm_tally_daily",
                "schedule_kind": "cron",
                "schedule_expr": "0 8 * * *",
                "lang": "en",
            }
        )
        self.assertTrue(out.get("ok"), out)
        job = out.get("job") or {}
        recipe = job.get("recipe") or {}
        self.assertTrue(recipe_has_playbook(recipe))
        self.assertEqual((recipe.get("source") or {}).get("template_id"), "ume_alarm_tally_daily")
        self.assertIn("UME", str(job.get("prompt_text") or ""))

    def test_create_auto_compiles_structured_prompt(self) -> None:
        prompt = (
            "Daily unmanaged dying-gasp correlation.\n\n"
            "Step 1 — Query BN EMS communication failures.\n"
            "Step 2 — Query remote dying gasp alarms.\n"
            "Step 3 — Correlate and attach XLSX report.\n"
        )
        out = schedule_create_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "name": "dying-gasp-daily",
                "prompt_text": prompt,
                "schedule_kind": "cron",
                "schedule_expr": "0 14 * * *",
                "lang": "en",
            }
        )
        self.assertTrue(out.get("ok"), out)
        recipe = (out.get("job") or {}).get("recipe") or {}
        self.assertTrue(recipe_has_playbook(recipe))
        self.assertGreaterEqual(len(recipe.get("steps") or []), 3)

    def test_simple_reminder_still_works(self) -> None:
        out = schedule_create_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "name": "喝水",
                "prompt_text": "提醒喝水",
                "schedule_kind": "interval",
                "schedule_expr": "10800",
            }
        )
        self.assertTrue(out.get("ok"), out)
        job = out.get("job") or {}
        self.assertEqual(job.get("prompt_text"), "提醒喝水")
        self.assertEqual(job.get("recipe") or {}, {})


if __name__ == "__main__":
    unittest.main()
