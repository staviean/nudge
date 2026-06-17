/* Nudge Card — live view with task actions (Phase 6a).
 * Read + act: complete, snooze, push-to-next, delete, toggle subtasks.
 * Create/edit forms come in 6b / Phase 7.
 */

const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function repeatText(t) {
  const f = t.frequency;
  const n = t.interval || 1;
  if (!f || f === "none") return "";
  if (f === "hourly") return n > 1 ? `every ${n} hours` : "hourly";
  if (f === "daily") return n > 1 ? `every ${n} days` : "daily";
  if (f === "weekly") {
    const base = n > 1 ? `every ${n} weeks` : "weekly";
    const days = (t.weekdays || []).map((d) => WD[d]).filter(Boolean).join(", ");
    return days ? `${base} on ${days}` : base;
  }
  if (f === "monthly") return n > 1 ? `every ${n} months` : "monthly";
  if (f === "yearly") return n > 1 ? `every ${n} years` : "yearly";
  return f;
}

function dueText(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString([], {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

class NudgeCard extends HTMLElement {
  setConfig(config) { this._config = config || {}; }
  getCardSize() { return 6; }

  set hass(hass) {
    this._hass = hass;
    if (!this._wired) {
      this._wired = true;
      this.addEventListener("click", (e) => this._onClick(e));
      this._subscribe();
    }
  }

  async _subscribe() {
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (data) => { this._data = data; this._render(); },
        { type: "nudge/subscribe" }
      );
    } catch (err) {
      this._renderError(err && err.message ? err.message : String(err));
    }
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
      this._wired = false;
    }
  }

  _onClick(e) {
    const el = e.target.closest("[data-action]");
    if (!el || !this._hass) return;
    const { action, uid, sub } = el.dataset;
    const task = ((this._data && this._data.tasks) || []).find((t) => t.uid === uid);
    const recurring = task && task.frequency && task.frequency !== "none";
    if (action === "complete") {
      this._do("complete_task", { uid }, recurring ? "Rolled to next occurrence" : "Task completed");
    } else if (action === "snooze") {
      this._do("snooze_task", { uid }, "Snoozed");
    } else if (action === "next") {
      this._do("push_to_next", { uid }, "Pushed to next occurrence");
    } else if (action === "subtask") {
      this._do("toggle_subtask", { task_uid: uid, subtask_uid: sub }, null);
    } else if (action === "delete") {
      if (window.confirm("Delete this task? This can't be undone.")) {
        this._do("delete_task", { uid }, "Task deleted");
      }
    }
  }

  async _do(service, data, successMsg) {
    try {
      await this._hass.callService("nudge", service, data);
      if (successMsg) this._toast(successMsg);
    } catch (err) {
      this._toast(`Error: ${err && err.message ? err.message : err}`);
    }
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message, duration: 3000 },
      bubbles: true,
      composed: true,
    }));
  }

  _renderError(msg) {
    this.innerHTML =
      `<ha-card header="Nudge"><div style="padding:16px;color:var(--error-color,#db4437)">` +
      `Couldn't load Nudge data: ${esc(msg)}</div></ha-card>`;
  }

  _render() {
    const d = this._data || { categories: [], tasks: [] };
    const cats = d.categories || [];
    const tasks = d.tasks || [];
    const byId = Object.fromEntries(cats.map((c) => [c.uid, c]));

    const groups = {};
    for (const t of tasks) {
      const k = t.category_id || "__none__";
      (groups[k] = groups[k] || []).push(t);
    }
    const order = cats.map((c) => c.uid);
    if (groups["__none__"]) order.push("__none__");

    let html = `<ha-card header="Nudge"><div style="padding:0 16px 16px">`;
    if (tasks.length === 0) {
      html += `<div style="padding:16px 0;color:var(--secondary-text-color)">No tasks yet.</div>`;
    }
    for (const k of order) {
      const list = groups[k] || [];
      if (!list.length) continue;
      const cat = byId[k];
      const name = cat ? cat.name : "Uncategorized";
      const color = cat && cat.color ? cat.color : "var(--primary-color)";
      html +=
        `<div style="margin-top:12px;font-weight:600;border-left:4px solid ${esc(color)};padding-left:8px">` +
        `${esc(name)}</div>`;
      for (const t of list) html += this._taskHtml(t);
    }
    html += `</div></ha-card>`;
    this.innerHTML = html;
  }

  _taskHtml(t) {
    const done = t.status === "completed";
    const uid = esc(t.uid);

    const meta = [];
    const due = dueText(t.due);
    if (due) meta.push(`⏰ ${esc(due)}`);
    const rep = repeatText(t);
    if (rep) meta.push(`\u{1F501} ${esc(rep)}`);
    const tg = t.notify_targets || [];
    if (tg.length) meta.push(`\u{1F4E3} ${esc(tg.join(", "))}`);

    const circle = done
      ? `<div style="font-size:18px;line-height:1.2;color:var(--secondary-text-color)">✓</div>`
      : `<div data-action="complete" data-uid="${uid}" title="Mark done" style="font-size:18px;line-height:1.2;cursor:pointer">○</div>`;

    const subs = t.subtasks || [];
    const subHtml = subs.length
      ? `<div style="margin:4px 0 0 24px">` +
        subs.map((s) =>
          `<div data-action="subtask" data-uid="${uid}" data-sub="${esc(s.uid)}" ` +
          `style="color:var(--secondary-text-color);cursor:pointer">${s.done ? "✓" : "○"} ${esc(s.summary)}</div>`
        ).join("") +
        `</div>`
      : "";

    const btn = (act, label, color) =>
      `<span data-action="${act}" data-uid="${uid}" style="cursor:pointer;font-size:12px;` +
      `color:${color};margin-right:14px">${label}</span>`;
    let actions = "";
    if (!done) {
      actions += btn("snooze", "Snooze", "var(--primary-color)");
      if (t.frequency && t.frequency !== "none") actions += btn("next", "Next", "var(--primary-color)");
    }
    actions += btn("delete", "Delete", "var(--error-color,#db4437)");
    const actionRow = `<div style="margin-top:6px">${actions}</div>`;

    return (
      `<div style="display:flex;gap:8px;padding:8px 0;border-bottom:1px solid var(--divider-color)">` +
      circle +
      `<div style="flex:1">` +
      `<div style="${done ? "text-decoration:line-through;color:var(--secondary-text-color)" : ""}">${esc(t.summary)}</div>` +
      (meta.length ? `<div style="font-size:12px;color:var(--secondary-text-color);margin-top:2px">${meta.join(" &nbsp; ")}</div>` : "") +
      subHtml +
      actionRow +
      `</div></div>`
    );
  }
}

if (!customElements.get("nudge-card")) {
  customElements.define("nudge-card", NudgeCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "nudge-card")) {
  window.customCards.push({
    type: "nudge-card",
    name: "Nudge",
    description: "Live view of your Nudge tasks",
    preview: false,
  });
}
console.info("%c NUDGE-CARD %c 6a (actions) ", "background:#3f51b5;color:#fff;border-radius:3px", "");
