# Nudge — Build Plan (Phases 4–7: Pilot)

Living planning doc. Goal of this arc: a **fully working pilot** — recurring tasks,
a usable management card, and per-task notification control — before IFTTT (deferred to Phase 8).

## Where we are (end of Chunk 3)

- Backend is solid: data models, persistent store, full `nudge.*` service surface,
  todo-list projection, and the background **nag engine** (push + TTS, quiet hours,
  snooze cap, mobile action buttons).
- `complete_task` already rolls a repeating task to its next occurrence **and resets
  subtasks to undone** — the Todoist behavior we *want* (no missed subtasks next cycle).
- Gaps: recurrence is coarse (no hourly / every-N / specific weekdays); announcement text
  is hardcoded; there is **no frontend read path and no card**; notify target is a single
  hardcoded entity/service; `manifest.json` lacks `frontend` and there is no `async_setup`.

## Locked decisions

- **Subtasks:** keep simple. Subtasks get their own optional custom announcement message;
  scheduling stays at the parent-task level; subtasks reset on parent roll (already built).
- **Notify field:** rename "Notify service override" → **"Send reminders to"**, with helper
  text: *"Leave blank to use your default. Pick a device to send just this task's reminders
  somewhere specific."*
- **Notify targets:** switch from a single value to a **list**, chosen via HA's device/target
  picker (friendly device names, multiple selection, by device/area/label). At send-time,
  resolve each target back to its `mobile_app` service so **action buttons survive**.
- **Card:** **no-build, single ES-module JS file** reusing HA's own components
  (`ha-form` / `ha-selector` / target picker). No webpack/Lit/TypeScript toolchain for the pilot.

## Guiding principle

Lock the data model first, then build the data pipe, then the UI. The card is built last so
the model never gets reworked underneath it. Every phase is independently testable.

---

## Phase 4 — Recurrence + model finalization (pure backend)

**Goal:** finalize the `Task`/`Subtask` shape and the recurrence engine; everything testable
via Developer Tools → Actions and unit tests, no frontend required.

- Extend recurrence: add `HOURLY`; add `interval` (every N) and `byday` (specific weekdays).
- Rewrite `Task.next_occurrence` to handle hourly / interval / weekday rules (hand-rolled,
  no new dependency; unit-tested).
- Add `announcement_message` to `Task` and `Subtask`; nag engine uses it when set, else falls
  back to the current summary/description message.
- Replace `notify_service: str` with `notify_targets: list` (read old field for back-compat).
  Nag engine loops over targets.
- Rename the notify field label + description in `services.yaml`; update service schemas.
- Storage: bump `STORAGE_MINOR_VERSION` + migration (defaults make this safe).

**Verify:** unit tests for `next_occurrence` across all frequencies/intervals/weekdays;
create/edit a recurring task via Developer Tools and confirm roll-forward + announcement.

**Delivers:** all new *capabilities* (hourly/weekday recurrence, custom announcements,
multi-target notify) usable headlessly.

## Phase 5 — Read API + card delivery pipeline (backend + throwaway-minimal card)

**Goal:** de-risk the frontend infrastructure behind ~30 lines of UI.

- WebSocket commands: `nudge/get_data` (categories + tasks), `nudge/subscribe_updates`
  (live push on `SIGNAL_STORE_UPDATED`), `nudge/version` (cache-bust check), and a
  notify-targets list for the picker.
- `frontend/` scaffolding: static-path registration + automatic Lovelace resource
  registration (per the HA 2026 embedded-card pattern).
- Add `frontend` to `manifest.json` dependencies; add `async_setup` for one-time registration.
- **Validate the notify-target → mobile_app-service resolution** against real devices here.
- Minimal read-only card that lists tasks live.

**Verify:** card appears in HA, shows live data, updates when the store changes; confirm
action buttons still fire from a resolved multi-target send.

**Delivers:** working end-to-end plumbing (backend ↔ card).

## Phase 6 — Card CRUD: create + manage (pilot core)

**Goal:** full task lifecycle from the card.

- Create/edit form: summary, description, **category dropdown**, due datetime,
  **recurrence builder** (frequency + interval + weekday picker), notification type,
  **"Send reminders to" multi-target picker**, nag settings, **announcement message**,
  subtask editor (with per-subtask announcement).
- List/manage view: complete, snooze, delete, push-to-next, subtask toggles.

**Verify:** create/manage every field combination from the card; confirm writes persist and
nags fire as configured.

**Delivers:** the usable pilot.

## Phase 7 — Edit, polish, pilot hardening

- Prefilled edit flow, category management UI, validation, empty states, version-mismatch
  reload toast, end-to-end pass.

**Delivers:** **fully working pilot.**

---

## Deferred (post-pilot)

- **Phase 8 — IFTTT** push (the existing `ifttt_event` field is already in the model).
- **Multi-user** (separate per-person task lists / quiet hours / permissions) — architectural;
  the list-based notify targets added in Phase 4 are a first step.

## Open technical risks to validate during the build

- Entity/target-based send vs. legacy `mobile_app` service for **action buttons** — resolution
  approach validated in Phase 5 against real devices.
- Storage migration safety on existing data (covered by tolerant `from_dict` + minor-version bump).
