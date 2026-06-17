# 💡 Ideas & Backlog

Parking lot for things that should **not** bloat the pilot. Promote to [[BUILD_PLAN]] when ready.
Record the reasoning for big ones in [[Decision-Log]].

## Deferred (already decided, post-pilot)

- **IFTTT push (Phase 8).** Model already carries an `ifttt_event` field. Wait until the pilot works.
- **Multi-user.** Separate per-person task lists, quiet hours, and permissions. Architectural; the
  list-based notify targets (Phase 4) are a first step, not the whole thing.

## Raw ideas (unsorted)

- Per-task "escalation": widen the audience or shorten the interval the longer a task stays undone.
- Snooze analytics: surface the most-snoozed tasks as a signal of avoidance (the README hints at this).
- Natural-language quick-add ("water plants every Tue and Fri at 6pm").
- Category-level defaults (a category sets default nag interval / notify targets for its tasks).
- "Focus mode" entity: temporarily suppress all nags except a chosen category.

## Questions to revisit

- How should multi-target sends interact with quiet hours per device/person?
- Do we want a weekly "what slipped" digest?
