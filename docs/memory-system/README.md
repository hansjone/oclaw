# Memory System Implementation

This folder implements a lightweight memory workflow based on:

- PARA for operational organization
- Atomic notes for reusable knowledge
- SRS for long-term retention
- Weekly review for maintenance and quality control

## Fixed PARA Containers

Do not change these top-level containers unless there is a major system redesign.

- `Projects`: time-bound outcomes with a deadline
- `Areas`: ongoing responsibilities without an end date
- `Resources`: reference topics and learning materials
- `Archives`: inactive content from all other containers
- `Inbox`: temporary capture queue before classification

Container contract and move rules are defined in `PARA.md`.

## Minimal Workflow (10-20 minutes/day)

1. Capture: move 3-5 raw items into `Inbox`.
2. Distill: convert 1-3 items into atomic notes under `Resources`.
3. Recall: generate 3-10 SRS cards using the conversion guide.
4. Express: produce one output (summary, answer, code note).

## Weekly Review (30 minutes/week)

Use `templates/weekly-review.md` to:

- empty inbox
- improve links
- archive stale items
- define next week's focus reviews

Use `weekly-review-schedule.md` to keep the review on a fixed weekly slot.

## Two-Week Minimum Rollout

- Week 1:
  - initialize PARA containers (`Projects`, `Areas`, `Resources`, `Archives`, `Inbox`)
  - capture and process notes daily using the workflow below
  - convert at least one high-value note/day into SRS cards
- Week 2:
  - enforce linking quality (each new note links to at least one existing note)
  - run one full weekly review
  - tune new-card load based on backlog and study time

## Templates

- `templates/atomic-note.md`
- `templates/srs-conversion.md`
- `templates/weekly-review.md`
- `templates/daily-routine.md`

## Folder Guidance

- `Projects/README.md`
- `Areas/README.md`
- `Resources/README.md`
- `Archives/README.md`
- `Inbox/README.md`

## Success Metrics

- 7 days: daily capture + review runs without backlog blow-up.
- 30 days: core topics can be recalled without opening source material.
- 60-90 days: writing/decision/coding reuse speed improves and repeated lookup drops.
- If review load is too high: reduce new cards first, keep only high-value knowledge.

## Automation Commands

Use the unified CLI to run this system with automatic recommendations:

- `powershell -ExecutionPolicy Bypass -File .\scripts\status_ops.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\start_ops.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\stop_ops.ps1`

Outputs are generated in `docs/memory-system/runs/`:

- `daily-YYYY-MM-DD.md`
- `weekly-YYYY-Www.md`

What is automated:

- fixed folder validation (`Projects/Areas/Resources/Archives/Inbox`)
- smart new-card limit recommendation (3-10/day based on backlog + inbox pressure)
- automatic focus ordering (`Projects > Areas > Resources`, weighted by active note volume)
