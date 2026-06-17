# 🧭 Decision Log

Lightweight record of choices and *why*, so future-you (and Claude) don't re-derive them.
Newest at the top. See also [[BUILD_PLAN]] and [[Ideas-Backlog]].

---

## 2026-06-17 — Phase 4 complete: recurrence, announcements, multi-target notify (backend)
**Decisions (implementation):**
- **Recurrence model:** added `HOURLY` + two `Task` fields — `interval` ("every N") and `weekdays`
  (0=Mon..6=Sun; `[]` = plain weekly). `next_occurrence` rewritten to advance **strictly past now**
  (fixes overdue re-nag loops) and to clamp month/leap ends with **no day-of-month drift**.
- **Announcements:** task `announcement_message` overrides the spoken TTS text; incomplete subtasks
  that carry their own message get appended. Push notifications still use summary/description.
- **Notify targets:** `notify_service` (single) → `notify_targets` (**list**); engine loops over all
  targets; field renamed **"Send reminders to"** with a notify-domain multi-entity picker. Storage
  bumped to **minor v2**; `from_dict` migrates old `notify_service` into the list.
**Why:** Covers "hourly/specific-days/etc." and multi-device family use without external deps
(hand-rolled recurrence) or breaking old data (tolerant `from_dict` + minor bump).
**Open risk (→ Phase 5):** picking a notify *entity* sends **plain** (no action buttons); buttons
still need a legacy `notify.mobile_app_*` service. Phase 5 will resolve a friendly entity pick back
to its service so buttons survive — to be validated against real devices.
**Status:** Backend complete and headlessly tested (recurrence unit tests + serialization/dispatch checks).

## 2026-06-16 — Subtasks stay simple (announcement-only)
**Decision:** Subtasks get their own optional custom announcement message, but **not** their own
schedule/recurrence. They reset to undone when the parent task rolls to its next occurrence.
**Why:** Covers the stated need without the model/engine/UI cost of independent subtask scheduling.
Also fixes a specific Todoist gripe — Todoist didn't roll subtasks over on parent completion, so
subtasks went missing the next cycle. Nudge's engine already resets them (`complete_task`).
**Status:** Locked for the pilot.

## 2026-06-16 — Notify field: "Send reminders to", as a multi-target list
**Decision:** Rename "Notify service override" → **"Send reminders to"**. Change the per-task value
from a single string to a **list of targets**, chosen via HA's device/target picker (friendly device
names, multiple selection). At send-time, resolve each target back to its `mobile_app` service so
**action buttons (Done/Snooze/Next) survive**.
**Why:** "Override" is dev-speak; the picker should show "John's Pixel," not `notify.mobile_app_*`.
List-based targets scale toward multi-device and eventually multi-family-member use. The button-vs-
entity tension is real (HA's entity send historically dropped action buttons), hence the resolution step.
**Status:** Locked; resolution path to be validated against real devices in Phase 5.

## 2026-06-16 — Recurrence: hand-rolled, no new dependency
**Decision:** Implement hourly / every-N / specific-weekday recurrence by hand in
`Task.next_occurrence` rather than pulling in `python-dateutil` / RRULE.
**Why:** The rule set is small and well-defined; hand-rolled keeps the integration dependency-free
and trivially unit-testable. Can graduate to RRULE later if rules get exotic.
**Status:** Locked for the pilot.

## 2026-06-16 — Card: no-build single JS file
**Decision:** Build the Lovelace card as one hand-authored ES-module file reusing HA's own
components (`ha-form`, `ha-selector`, target picker). No webpack/Lit/TypeScript toolchain.
**Why:** Fastest iteration for a pilot, no Node build step, and readable/tweakable by the owner.
Logic ports to Lit later if Nudge becomes a large published project.
**Status:** Locked for the pilot.

## 2026-06-16 — Repo hygiene: single source of truth + LF line endings
**Decision:** Do all work in the git repo at `S:\WhereIsMyMind\Nudge` (not a second Cowork copy).
Added `.gitattributes` (`* text=auto eol=lf`) and normalized line endings.
**Why:** Two copies drift and force manual reconciliation. Mixed CRLF/LF produced phantom whole-file
diffs; normalizing to LF makes `git diff` trustworthy.
**Status:** Done (committed).
