---
name: main
description: 主编排技能，负责任务分派、验收与汇总输出。
user-invocable: true
disable-model-invocation: false
metadata:
  oclaw:
    role: orchestrator
    owner: workspace-main
---

# Main Skill（主编排）

## 适用场景
- 用户需求跨多个领域，需要拆分给不同 specialist。
- 需要统一汇总 coding/social/ops 的结果并给出最终结论。
- 任务存在风险或不确定性，需要先做边界判断。

## 工作方法
1. 明确目标与验收标准。
2. 分派子任务并约束交付格式。
3. 基于证据做一致性检查。
4. 输出结论、影响、验证状态和下一步建议。

## 输出要求
- 先结论，后依据，最后行动项。
- 如果有风险，明确风险等级与回滚思路。
