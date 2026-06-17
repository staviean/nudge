/* Nudge Card — minimal live view (read-only).
 * Phase 5b: subscribes to nudge/subscribe and renders categories + tasks.
 * Editing/CRUD comes in Phase 6.
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
  setConfig(config) {
    this._config = config || {};
  }

  getCardSize() {
    return 6;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._subscribed) {
      this._subscribed = true;
      this._subscribe();
    }
  }

  async _subscribe() {
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (data) => {
          this._data = data;
          this._render();
        },
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
      this._subscribed = false;
    }
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
      html +=
        `<div style="padding:16px 0;color:var(--secondary-text-color)">` +
        `No tasks yet. Create one with the <code>nudge.create_task</code> action.</div>`;
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
    const meta = [];
    const due = dueText(t.due);
    if (due) meta.push(`⏰ ${esc(due)}`);
    const rep = repeatText(t);
    if (rep) meta.push(`\u{1F501} ${esc(rep)}`);
    const tg = t.notify_targets || [];
    if (tg.length) meta.push(`\u{1F4E3} ${esc(tg.join(", "))}`);

    const subs = t.subtasks || [];
    const subHtml = subs.length
      ? `<div style="margin:4px 0 0 24px">` +
        subs
          .map(
            (s) =>
              `<div style="color:var(--secondary-text-color)">${s.done ? "✓" : "○"} ${esc(s.summary)}</div>`
          )
          .join("") +
        `</div>`
      : "";

    return (
      `<div style="display:flex;gap:8px;padding:8px 0;border-bottom:1px solid var(--divider-color)">` +
      `<div style="font-size:18px;line-height:1.2">${done ? "✓" : "○"}</div>` +
      `<div style="flex:1">` +
      `<div style="${done ? "text-decoration:line-through;color:var(--secondary-text-color)" : ""}">${esc(t.summary)}</div>` +
      (meta.length
        ? `<div style="font-size:12px;color:var(--secondary-text-color);margin-top:2px">${meta.join(" &nbsp; ")}</div>`
        : "") +
      subHtml +
      `</div></div>`
    );
  }
}

customElements.define("nudge-card", NudgeCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "nudge-card",
  name: "Nudge",
  description: "Live view of your Nudge tasks",
  preview: false,
});
console.info("%c NUDGE-CARD %c loaded ", "background:#3f51b5;color:#fff;border-radius:3px", "");
