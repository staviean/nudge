# 🏠 Nudge — Home

The map of content for this project's knowledge base. Start here.

> Nudge is a neurodivergent-friendly, fully-local task manager for Home Assistant,
> built around **nag notifications** that persist until a task is done.

## Core docs

- [[BUILD_PLAN]] — the phased build plan (currently: **Phase 4, pilot arc**)
- [[Decision-Log]] — why we built things the way we did
- [[Ideas-Backlog]] — parked ideas and deferred features
- [[Family-Task-Model.canvas|Family Task Model (Canvas)]] — visual modeling of real task hierarchies

## Current status

- **Done:** Chunks 1–3 (data model, store, services, todo platform, nag engine).
- **Next:** Phase 4 — recurrence engine + model finalization (hourly / every-N / specific
  weekdays, per-task & per-subtask announcements, multi-target notify).

## How to use this vault

- The vault is the **repo root**, so notes live with the code and are version-controlled together.
- Link notes with `[[double brackets]]`. Unresolved links are fine — they're a to-do for a note
  that doesn't exist yet.
- Code lives in `custom_components/nudge/` — edit that in your IDE, not here. This vault is for
  thinking, deciding, and remembering.
