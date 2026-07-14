from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.scheduler.recipe import (
    compile_playbook_instruction,
    looks_like_complex_schedule_prompt,
    normalize_recipe,
    preview_markdown,
    prompt_summary_from_recipe,
    recipe_has_playbook,
    recipe_missing_fields,
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
