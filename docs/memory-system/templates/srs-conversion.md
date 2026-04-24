# Note to SRS Conversion Rules

## Goal

Convert high-value atomic notes into testable cards with sustainable daily load.

## Daily Limits

- New cards/day: `max 10` (default target: 3-10)
- Review cards/day: no hard cap, but keep total study time under 20 minutes
- If overload happens: reduce new cards first, never skip due reviews

## Priority Queue for New Cards

Create cards in this order:

1. Current project-critical knowledge (`Projects`)
2. Frequently used responsibility knowledge (`Areas`)
3. Long-term leverage concepts (`Resources`)
4. Nice-to-know trivia (only if capacity remains)

## Intake Pipeline (Note -> Card)

1. Pick up to 3 atomic notes from today's distillation.
2. Score each note quickly:
   - Impact (0-2): helps current projects or repeated decisions
   - Frequency (0-2): likely reused this week
   - Forget risk (0-2): easy to forget if not reviewed
3. Convert highest scores first (max total new cards/day = 10).
4. Postpone low-score notes to next day instead of forcing more cards.

## Conversion Checklist

For each atomic note:

1. Keep one card for one testable idea.
2. Prefer short answer or cloze over long text.
3. Remove context that gives away the answer.
4. Add source tag for traceability.
5. Add topic tag for filtering (`project/*`, `area/*`, `resource/*`).

## Card Formats

### Q/A

- Front: precise question
- Back: one-sentence answer + optional example

### Cloze

- Sentence must be meaningful without extra paragraph context.
- Hide one concept at a time.

## Quality Standard

- Answer length under 20 words when possible.
- Each card should be answerable within 10 seconds.
- If answer is ambiguous, split into multiple cards.

## Weekly Tuning

- Suspend low-value or repeated-failure cards with weak real-world relevance.
- Merge duplicate cards.
- Promote high-utility cards into a "core deck" tag.
