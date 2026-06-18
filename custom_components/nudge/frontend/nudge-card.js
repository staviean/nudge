/* Nudge Card — live view, actions, and a native create dialog (Phase 6b, rev 2).
 * Self-contained modal with native inputs (no ha-form/ha-dialog dependency).
 */
const WD = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const WD_FULL = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function repeatText(t){const f=t.frequency,n=t.interval||1;if(!f||f==="none")return"";if(f==="hourly")return n>1?`every ${n} hours`:"hourly";if(f==="daily")return n>1?`every ${n} days`:"daily";if(f==="weekly"){const b=n>1?`every ${n} weeks`:"weekly";const d=(t.weekdays||[]).map((x)=>WD[x]).filter(Boolean).join(", ");return d?`${b} on ${d}`:b;}if(f==="monthly")return n>1?`every ${n} months`:"monthly";if(f==="yearly")return n>1?`every ${n} years`:"yearly";return f;}
function dueText(iso){if(!iso)return"";const d=new Date(iso);if(isNaN(d.getTime()))return"";return d.toLocaleString([],{weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});}

class NudgeCard extends HTMLElement {
  setConfig(config){this._config=config||{};}
  getCardSize(){return 6;}
  set hass(hass){this._hass=hass;if(!this._wired){this._wired=true;this.addEventListener("click",(e)=>this._onClick(e));this._subscribe();}}
  async _subscribe(){try{this._unsub=await this._hass.connection.subscribeMessage((data)=>{this._data=data;this._render();},{type:"nudge/subscribe"});}catch(err){this._renderError(err&&err.message?err.message:String(err));}}
  disconnectedCallback(){if(this._unsub){this._unsub();this._unsub=null;this._wired=false;}}

  _onClick(e){
    const el=e.target.closest("[data-action]");if(!el||!this._hass)return;
    const {action,uid,sub}=el.dataset;
    if(action==="add"){this._openCreate();return;}
    const task=((this._data&&this._data.tasks)||[]).find((t)=>t.uid===uid);
    const recurring=task&&task.frequency&&task.frequency!=="none";
    if(action==="complete")this._do("complete_task",{uid},recurring?"Rolled to next occurrence":"Task completed");
    else if(action==="snooze")this._do("snooze_task",{uid},"Snoozed");
    else if(action==="next")this._do("push_to_next",{uid},"Pushed to next occurrence");
    else if(action==="subtask")this._do("toggle_subtask",{task_uid:uid,subtask_uid:sub},null);
    else if(action==="delete"){if(window.confirm("Delete this task? This can't be undone."))this._do("delete_task",{uid},"Task deleted");}
  }
  async _do(service,data,m){try{await this._hass.callService("nudge",service,data);if(m)this._toast(m);}catch(err){this._toast(`Error: ${err&&err.message?err.message:err}`);}}
  _toast(message){this.dispatchEvent(new CustomEvent("hass-notification",{detail:{message,duration:3000},bubbles:true,composed:true}));}

  _openCreate(){
    const hass=this._hass;
    const cats=((this._data&&this._data.categories)||[]);
    const fname=(e)=>(hass.states[e]&&hass.states[e].attributes&&hass.states[e].attributes.friendly_name)||e;
    const notifyEnts=Object.keys(hass.states||{}).filter((e)=>e.startsWith("notify.")).sort();

    const overlay=document.createElement("div");
    overlay.style.cssText="position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.5);display:flex;align-items:flex-start;justify-content:center;overflow:auto;padding:5vh 12px";
    const panel=document.createElement("div");
    panel.style.cssText="background:var(--ha-card-background,var(--card-background-color,#1c1c1c));color:var(--primary-text-color,#e1e1e1);border-radius:12px;max-width:480px;width:100%;padding:20px;box-sizing:border-box;box-shadow:0 10px 40px rgba(0,0,0,0.5)";
    panel.addEventListener("click",(e)=>e.stopPropagation());

    const fld="display:block;width:100%;box-sizing:border-box;margin:4px 0 14px;padding:8px 10px;border-radius:6px;border:1px solid var(--divider-color,#444);background:var(--secondary-background-color,#2a2a2a);color:inherit;font-size:14px;color-scheme:light dark";
    const lbl="display:block;font-size:13px;font-weight:600;color:var(--secondary-text-color)";
    const catOpts=`<option value="__none__">Uncategorized</option>`+cats.map((c)=>`<option value="${esc(c.uid)}">${esc(c.name)}</option>`).join("");
    const freqOpts=["none","hourly","daily","weekly","monthly","yearly"].map((v)=>`<option value="${v}">${v[0].toUpperCase()+v.slice(1)}</option>`).join("");
    const notifOpts=[["none","None"],["push","Push notification"],["announce","Announce (TTS)"],["both","Both"]].map(([v,l])=>`<option value="${v}">${l}</option>`).join("");
    const notifyChecks=notifyEnts.length?notifyEnts.map((e)=>`<label style="display:block;font-size:14px;margin:3px 0"><input type="checkbox" data-ntarget value="${esc(e)}"> ${esc(fname(e))}</label>`).join(""):`<div style="color:var(--secondary-text-color);font-size:13px">No notify devices found.</div>`;
    const wdChecks=WD_FULL.map((d,i)=>`<label style="display:inline-block;font-size:13px;margin:0 10px 4px 0"><input type="checkbox" data-wd value="${i}"> ${d.slice(0,3)}</label>`).join("");

    panel.innerHTML=
      `<div style="font-size:18px;font-weight:700;margin-bottom:14px">New task</div>`+
      `<label style="${lbl}">Task name *</label><input id="n-summary" type="text" style="${fld}" placeholder="e.g. Take out the trash">`+
      `<label style="${lbl}">Category</label><select id="n-cat" style="${fld}">${catOpts}</select>`+
      `<label style="${lbl}">Description</label><textarea id="n-desc" rows="2" style="${fld}"></textarea>`+
      `<label style="${lbl}">Due date</label><input id="n-date" type="date" style="${fld}">`+
      `<label style="${lbl}">Due time</label><input id="n-time" type="time" style="${fld}">`+
      `<label style="${lbl}">Repeat</label><select id="n-freq" style="${fld}">${freqOpts}</select>`+
      `<div id="n-iv-row" style="display:none"><label style="${lbl}" id="n-iv-lbl">Repeat every</label><input id="n-iv" type="number" min="1" max="365" value="1" style="${fld}"></div>`+
      `<div id="n-wd-row" style="display:none"><label style="${lbl}">On weekdays</label><div style="margin:4px 0 14px">${wdChecks}</div></div>`+
      `<label style="${lbl}">Notify by</label><select id="n-notif" style="${fld}">${notifOpts}</select>`+
      `<label style="${lbl}">Send reminders to</label><div style="margin:4px 0 14px;max-height:140px;overflow:auto;border:1px solid var(--divider-color,#444);border-radius:6px;padding:8px">${notifyChecks}</div>`+
      `<label style="${lbl}">Custom announcement</label><textarea id="n-ann" rows="2" style="${fld}"></textarea>`+
      `<label style="${lbl}" title="Repeat the notification until you complete or snooze the task"><input id="n-nag" type="checkbox"> Nag until done</label><div style="height:10px"></div>`+
      `<label style="${lbl}">Nag interval (minutes)</label><input id="n-nagint" type="number" min="1" max="1440" style="${fld}">`+
      `<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:8px">`+
      `<button id="n-cancel" style="cursor:pointer;border:none;border-radius:6px;padding:9px 16px;font-weight:600;background:transparent;color:var(--primary-color)">Cancel</button>`+
      `<button id="n-save" style="cursor:pointer;border:none;border-radius:6px;padding:9px 18px;font-weight:600;background:var(--primary-color);color:var(--text-primary-color,#fff)">Create task</button></div>`;

    overlay.appendChild(panel);
    overlay.addEventListener("click",()=>overlay.remove());
    document.body.appendChild(overlay);

    const q=(id)=>panel.querySelector(id);
    const freqSel=q("#n-freq");
    const syncFreq=()=>{
      const f=freqSel.value;
      q("#n-iv-row").style.display=f==="none"?"none":"block";
      q("#n-wd-row").style.display=f==="weekly"?"block":"none";
      const unit={hourly:"hours",daily:"days",weekly:"weeks",monthly:"months",yearly:"years"}[f]||"times";
      q("#n-iv-lbl").textContent=`Repeat every — how many ${unit}?`;
    };
    freqSel.addEventListener("change",syncFreq);syncFreq();
    q("#n-cancel").addEventListener("click",()=>overlay.remove());
    q("#n-save").addEventListener("click",()=>this._submitCreate(panel,overlay));
    q("#n-summary").focus();
  }

  async _submitCreate(panel,overlay){
    const q=(id)=>panel.querySelector(id);
    const summary=q("#n-summary").value.trim();
    if(!summary){this._toast("Task name is required");return;}
    const payload={summary};
    const cat=q("#n-cat").value;if(cat&&cat!=="__none__")payload.category_id=cat;
    const desc=q("#n-desc").value.trim();if(desc)payload.description=desc;
    const date=q("#n-date").value;if(date)payload.due=`${date}T${q("#n-time").value||"09:00"}:00`;
    const freq=q("#n-freq").value;
    if(freq&&freq!=="none"){
      payload.frequency=freq;
      const iv=parseInt(q("#n-iv").value,10);if(iv>1)payload.interval=iv;
      if(freq==="weekly"){const wd=[...panel.querySelectorAll("[data-wd]:checked")].map((c)=>parseInt(c.value,10));if(wd.length)payload.weekdays=wd;}
    }
    const notif=q("#n-notif").value;if(notif&&notif!=="none")payload.notification_type=notif;
    const targets=[...panel.querySelectorAll("[data-ntarget]:checked")].map((c)=>c.value);if(targets.length)payload.notify_targets=targets;
    const ann=q("#n-ann").value.trim();if(ann)payload.announcement_message=ann;
    if(q("#n-nag").checked)payload.nag_enabled=true;
    const ni=parseInt(q("#n-nagint").value,10);if(ni>=1)payload.nag_interval_minutes=ni;
    try{await this._hass.callService("nudge","create_task",payload);this._toast("Task created");overlay.remove();}
    catch(err){this._toast(`Error: ${err&&err.message?err.message:err}`);}
  }

  _renderError(msg){this.innerHTML=`<ha-card header="Nudge"><div style="padding:16px;color:var(--error-color,#db4437)">Couldn't load Nudge data: ${esc(msg)}</div></ha-card>`;}
  _render(){
    const d=this._data||{categories:[],tasks:[]};const cats=d.categories||[],tasks=d.tasks||[];
    const byId=Object.fromEntries(cats.map((c)=>[c.uid,c]));
    const groups={};for(const t of tasks){const k=t.category_id||"__none__";(groups[k]=groups[k]||[]).push(t);}
    const order=cats.map((c)=>c.uid);if(groups["__none__"])order.push("__none__");
    let html=`<ha-card header="Nudge"><div style="padding:0 16px 16px">`;
    html+=`<div style="padding:12px 0"><span data-action="add" style="cursor:pointer;color:var(--primary-color);font-weight:600">+ Add task</span></div>`;
    if(tasks.length===0)html+=`<div style="padding:8px 0;color:var(--secondary-text-color)">No tasks yet — add one above.</div>`;
    for(const k of order){const list=groups[k]||[];if(!list.length)continue;const cat=byId[k];const name=cat?cat.name:"Uncategorized";const color=cat&&cat.color?cat.color:"var(--primary-color)";html+=`<div style="margin-top:12px;font-weight:600;border-left:4px solid ${esc(color)};padding-left:8px">${esc(name)}</div>`;for(const t of list)html+=this._taskHtml(t);}
    html+=`</div></ha-card>`;this.innerHTML=html;
  }
  _taskHtml(t){
    const done=t.status==="completed";const uid=esc(t.uid);
    const meta=[];const due=dueText(t.due);if(due)meta.push(`⏰ ${esc(due)}`);const rep=repeatText(t);if(rep)meta.push(`\u{1F501} ${esc(rep)}`);const tg=t.notify_targets||[];if(tg.length)meta.push(`\u{1F4E3} ${esc(tg.join(", "))}`);
    const circle=done?`<div style="font-size:18px;line-height:1.2;color:var(--secondary-text-color)">✓</div>`:`<div data-action="complete" data-uid="${uid}" title="Mark done" style="font-size:18px;line-height:1.2;cursor:pointer">○</div>`;
    const subs=t.subtasks||[];const subHtml=subs.length?`<div style="margin:4px 0 0 24px">`+subs.map((s)=>`<div data-action="subtask" data-uid="${uid}" data-sub="${esc(s.uid)}" style="color:var(--secondary-text-color);cursor:pointer">${s.done?"✓":"○"} ${esc(s.summary)}</div>`).join("")+`</div>`:"";
    const btn=(a,l,c)=>`<span data-action="${a}" data-uid="${uid}" style="cursor:pointer;font-size:12px;color:${c};margin-right:14px">${l}</span>`;
    let actions="";if(!done){actions+=btn("snooze","Snooze","var(--primary-color)");if(t.frequency&&t.frequency!=="none")actions+=btn("next","Next","var(--primary-color)");}actions+=btn("delete","Delete","var(--error-color,#db4437)");
    return `<div style="display:flex;gap:8px;padding:8px 0;border-bottom:1px solid var(--divider-color)">`+circle+`<div style="flex:1"><div style="${done?"text-decoration:line-through;color:var(--secondary-text-color)":""}">${esc(t.summary)}</div>`+(meta.length?`<div style="font-size:12px;color:var(--secondary-text-color);margin-top:2px">${meta.join(" &nbsp; ")}</div>`:"")+subHtml+`<div style="margin-top:6px">${actions}</div></div></div>`;
  }
}
if(!customElements.get("nudge-card"))customElements.define("nudge-card",NudgeCard);
window.customCards=window.customCards||[];
if(!window.customCards.some((c)=>c.type==="nudge-card"))window.customCards.push({type:"nudge-card",name:"Nudge",description:"Live view and management of your Nudge tasks",preview:false});
console.info("%c NUDGE-CARD %c 6b native form ","background:#3f51b5;color:#fff;border-radius:3px","");
