---
name: coding
description: 研发实现技能，负责代码实现、缺陷修复与验证闭环。
user-invocable: true
disable-model-invocation: false
metadata:
  openclaw:
    role: specialist
    owner: workspace-coding
    focus:
      - implement
      - refactor
      - test
---

# Coding Skill（研发实现）

## 适用场景
- 新功能开发、缺陷修复、重构和性能优化。
- 需要定位报错、复现问题并给出稳定修复方案。
- 需要输出可合并、可验证、可回滚的代码结果。

## 工作方法
1. 先复现问题，明确预期行为。
2. 设计最小改动方案，控制影响面。
3. 实施修改并运行相关测试。
4. 提供变更说明、验证结果和残余风险。

## 输出要求
- 必须包含：改了什么、为什么、怎么验证、还有什么风险。
- 避免顺手混改无关逻辑。
