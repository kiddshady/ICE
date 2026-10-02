// DE4DC0DEX · simulador. La página no decide nada: le manda cada acción al cerebro
// (POST /api) y dibuja lo que vuelve. Todo lo que ves en "Por qué" lo escribió
// el cerebro de Python, no este archivo.

const $ = (sel) => document.querySelector(sel);

// ------------------------------------------------------------ estado de la página

let snap = null;        // la última foto que mandó el servidor
let snapAt = 0;         // cuándo llegó (performance.now), para que el reloj corra
let active = 1;         // quién escribe
let replyTo = null;     // { msg_id, name, text }
let forwarded = false;

const HUES = [215, 300, 150, 60, 20, 180, 260, 100, 330, 40];
const hue = (id) => (id === 0 ? "var(--accent)" : `oklch(0.8 0.1 ${HUES[(id - 1) % HUES.length]})`);

// ------------------------------------------------------------ servidor

async function send(cmd) {
  const res = await fetch("/api", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cmd),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  render(data);
  if (data.notice) toast(data.notice, data.notice.startsWith("Telegram bloquea"));
  return data;
}

// ------------------------------------------------------------ utilidades

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function icon(name) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "icon");
  const use = document.createElementNS(ns, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

const pad = (n) => String(Math.floor(n)).padStart(2, "0");

function clock(sec) {
  const d = Math.floor(sec / 86400);
  const rest = sec % 86400;
  const hms = `${pad(rest / 3600)}:${pad((rest % 3600) / 60)}:${pad(rest % 60)}`;
  return d > 0 ? `${d} d ${hms}` : hms;
}

function left(sec) {
  sec = Math.max(0, Math.ceil(sec));
  if (sec >= 3600) return `${Math.floor(sec / 3600)} h ${pad((sec % 3600) / 60)} min`;
  return `${Math.floor(sec / 60)}:${pad(sec % 60)}`;
}

const nowLocal = () => (snap ? snap.now + (performance.now() - snapAt) / 1000 : 0);
const drift = () => nowLocal() - (snap ? snap.now : 0);

// ------------------------------------------------------------ dibujo

const chatNodes = [];
const traceCount = { why: 0, log: 0 };
const personNodes = new Map();

function render(data) {
  const wasReset = snap && data.chat.length < chatNodes.length;
  snap = data;
  snapAt = performance.now();
  if (wasReset) clearAll();
  if (!data.people.some((p) => p.id === active)) active = data.people[0].id;
  renderPeople();
  renderChat();
  renderTraces();
  renderLog();
  renderComposer();
}

function clearAll() {
  chatNodes.length = 0;
  $("#chat").replaceChildren();
  for (const el of [...$("#why").querySelectorAll(".trace")]) el.remove();
  for (const el of [...$("#log").querySelectorAll(".log-line")]) el.remove();
  traceCount.why = traceCount.log = 0;
  for (const node of personNodes.values()) node.remove();
  personNodes.clear();
  replyTo = null;
}

// ---- personas

function badgesFor(p) {
  const out = [];
  const d = drift();
  if (p.admin) out.push({ key: "admin", cls: "accent", label: "admin" });
  if (p.banned) out.push({ key: "ban", cls: "danger", label: "con ban" });
  else if (!p.present) out.push({ key: "out", label: "afuera" });
  if (p.verify_left != null)
    out.push({ key: "verify", cls: "accent", label: "verificando", time: left(p.verify_left - d) });
  if (p.mute_left != null)
    out.push({ key: "mute", cls: "danger", label: "en silencio", time: left(p.mute_left - d) });
  if (p.newcomer_left != null && p.verify_left == null)
    out.push({ key: "new", label: "período inicial", time: left(p.newcomer_left - d) });
  if (p.warns > 0) out.push({ key: "warns", label: "advertencias", warns: p.warns });
  return out;
}

function syncBadges(box, list) {
  const keep = new Set(list.map((b) => b.key));
  for (const el of [...box.children]) {
    if (!keep.has(el.dataset.key) && !el.classList.contains("bye")) {
      el.classList.add("bye");
      setTimeout(() => el.remove(), 220);
    }
  }
  for (const b of list) {
    let el = box.querySelector(`[data-key="${b.key}"]:not(.bye)`);
    if (!el) {
      el = h("span", { class: `badge ${b.cls || ""}`, "data-key": b.key });
      box.append(el);
    }
    const sig = `${b.label}|${b.time ?? ""}|${b.warns ?? ""}`;
    if (el.dataset.sig === sig) continue;
    el.dataset.sig = sig;
    if (b.warns != null) {
      const dots = h("span", { class: "warn-dots" },
        Array.from({ length: snap.max_warns }, (_, i) => h("i", { class: i < b.warns ? "on" : "" })));
      el.replaceChildren(dots, `${b.warns}/${snap.max_warns}`);
    } else {
      el.replaceChildren(b.label, b.time ? h("span", { class: "mono" }, b.time) : "");
    }
  }
}

function renameOpen(node, open) {
  const form = node.querySelector(".rename-row");
  const input = form.querySelector(".field");
  node.classList.toggle("is-renaming", open);
  form.inert = !open;
  if (open) {
    input.value = snap.people.find((x) => x.id === Number(node.dataset.id)).name;
    input.focus({ preventScroll: true });
    input.select();
  }
}

function personNode(p) {
  const node = h("div", { class: "person", style: `--hue:${hue(p.id)}`, tabindex: "0", "data-id": p.id },
    h("div", { class: "avatar" }),
    h("div", { class: "person-main" },
      h("div", { class: "person-name" }),
      h("div", { class: "person-role" }, h("span", { class: "person-handle mono" }, `@${p.username}`), ` · ${p.role}`),
      h("div", { class: "badges" })),
    h("div", { class: "person-tools" },
      h("button", { class: "rename-btn", type: "button" }, icon("pencil")),
      h("button", { class: "presence-btn", type: "button" })),
    h("form", { class: "rename-row", autocomplete: "off", inert: true },
      h("div", { class: "rename-inner" },
        h("input", { class: "field", maxlength: "24", "aria-label": "Nombre nuevo" }),
        h("button", { class: "icon-btn", type: "submit", "data-tip": "Cambiar el nombre", "aria-label": "Cambiar el nombre" },
          icon("pass")))));

  node.addEventListener("click", (e) => {
    if (e.target.closest(".person-tools, .rename-row")) return;
    active = p.id;
    replyTo = null;
    renderPeople();
    renderComposer();
    $("#text").focus();
  });
  node.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target === node) node.click();
  });
  node.querySelector(".presence-btn").addEventListener("click", () => {
    const person = snap.people.find((x) => x.id === p.id);
    send({ op: person.present ? "leave" : "join", user: p.id });
  });

  const form = node.querySelector(".rename-row");
  node.querySelector(".rename-btn").addEventListener("click", () =>
    renameOpen(node, !node.classList.contains("is-renaming")));
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = form.querySelector(".field").value.trim();
    renameOpen(node, false);
    if (name) send({ op: "rename", user: p.id, name });
  });
  form.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { renameOpen(node, false); node.focus(); }
  });
  // Si el foco se va de la tarjeta, el cambio se descarta.
  form.addEventListener("focusout", (e) => {
    if (!node.contains(e.relatedTarget)) renameOpen(node, false);
  });
  return node;
}

function renderPeople() {
  const box = $("#people");
  for (const p of snap.people) {
    let node = personNodes.get(p.id);
    if (!node) {
      node = personNode(p);
      personNodes.set(p.id, node);
      box.append(node);
    }
    node.classList.toggle("is-active", p.id === active);
    node.classList.toggle("is-out", !p.present);

    const renamed = node.dataset.name !== undefined && node.dataset.name !== p.name;
    if (node.dataset.name !== p.name) {
      node.dataset.name = p.name;
      const nameEl = node.querySelector(".person-name");
      const avatar = node.querySelector(".avatar");
      nameEl.textContent = p.name;
      avatar.textContent = p.name.slice(0, 1).toUpperCase();
      const tip = `Cambiarle el nombre a ${p.name}`;
      const rb = node.querySelector(".rename-btn");
      rb.dataset.tip = tip;
      rb.setAttribute("aria-label", tip);
      if (renamed) {
        const rise = [{ opacity: 0, transform: "translateY(5px)" }, { opacity: 1, transform: "none" }];
        for (const el of [nameEl, avatar]) el.animate(rise, { duration: 320, easing: "cubic-bezier(.16, 1, .3, 1)" });
      }
    }

    const btn = node.querySelector(".presence-btn");
    const mode = p.present ? "out" : "in";
    if (btn.dataset.mode !== mode || renamed) {
      if (btn.dataset.mode !== mode) btn.replaceChildren(icon(mode));
      btn.dataset.mode = mode;
      btn.dataset.tip = p.present ? `Hacer que ${p.name} se vaya del grupo` : `Hacer que ${p.name} entre al grupo`;
      btn.setAttribute("aria-label", btn.dataset.tip);
    }
    syncBadges(node.querySelector(".badges"), badgesFor(p));
  }
}

// ---- chat

function msgNode(m) {
  if (m.kind === "system") return h("div", { class: "sys" }, m.text);
  const isBot = m.kind === "bot";
  const node = h("div", { class: `msg ${isBot ? "bot" : ""}`, style: `--hue:${hue(m.user_id)}` },
    h("div", { class: "msg-head" },
      h("span", { class: "msg-name" }, m.name),
      h("span", { class: "msg-edited", hidden: !m.edited }, "editado"),
      h("span", { class: "msg-time mono" }, clock(m.at))),
    m.forwarded && h("div", { class: "msg-tag" }, icon("forward"), "Reenviado de un canal"),
    m.reply && h("div", { class: "quote" }, h("b", {}, m.reply.name), " ", m.reply.text),
    m.photos && h("div", { class: "msg-tag" }, icon("album"), `Álbum de ${m.photos.length} fotos`),
    m.photos && h("div", { class: "album" }, m.photos.map(() => h("span", { class: "album-tile" }))),
    h("div", { class: "msg-text" }, m.text),  // vacío en un álbum sin texto: no se ve
    m.button && h("button", {
      class: "msg-button", type: "button",
      onclick: () => send({ op: "press", user: active, data: m.button.data }),
    }, m.button.label),
    h("div", { class: "deleted-note" }, h("span", {}, icon("trash"), "Borrado por DE4DC0DEX")),
    h("button", {
      class: "icon-btn small msg-reply", type: "button", "data-tip": "Responder", "aria-label": "Responder",
      onclick: () => {
        replyTo = { msg_id: m.msg_id, name: m.name, text: m.text || `Álbum de ${m.photos.length} fotos` };
        renderComposer(); $("#text").focus();
      },
    }, icon("reply")));
  node.shownText = m.text;
  return node;
}

function renderChat() {
  const box = $("#chat");
  let added = 0;
  snap.chat.forEach((m, i) => {
    let node = chatNodes[i];
    // Un mensaje editado cambia el texto en el lugar, sin rearmarse: así el
    // borrado que venga con la edición entra con su transición.
    if (node && m.kind === "user" && node.shownText !== m.text) {
      node.querySelector(".msg-text").textContent = m.text;
      node.querySelector(".msg-edited").hidden = !m.edited;
      node.shownText = m.text;
    }
    if (!node) {
      node = msgNode(m);
      chatNodes[i] = node;
      box.append(node);
      added++;
    }
    if (m.kind !== "system") {
      node.classList.toggle("is-deleted", m.deleted);
      const btn = node.querySelector(".msg-button");
      if (btn) btn.disabled = m.deleted;
    }
  });
  if (added) requestAnimationFrame(() => box.scrollTo({ top: box.scrollHeight, behavior: "smooth" }));
}

// ---- por qué y registro

function traceNode(t) {
  const node = h("article", { class: "trace is-new" },
    h("div", { class: "trace-head" },
      h("span", { class: "trace-n mono" }, `#${t.n}`),
      h("span", { class: "trace-title" }, t.title),
      h("span", { class: "trace-time mono" }, clock(t.at))),
    t.blocked && h("div", { class: "blocked" }, icon("block"), "Telegram lo frena antes de que llegue al bot"),
    h("ul", { class: "steps" }, t.steps.map((s) =>
      h("li", { class: `step ${s.verdict}` },
        icon(s.verdict),
        h("div", {}, h("div", { class: "step-rule" }, s.rule), h("div", { class: "step-detail" }, s.detail))))),
    t.actions.length > 0 && h("div", { class: "calls" },
      h("div", { class: "calls-title" }, "Llamadas a Telegram"),
      t.actions.map((a) => h("div", { class: "call" },
        h("span", { class: "call-api" }, a.api),
        h("span", { class: "call-detail" }, a.detail)))));
  setTimeout(() => node.classList.remove("is-new"), 1800);
  return node;
}

function renderTraces() {
  const box = $("#why");
  const empty = $("#why-empty");
  const fresh = snap.traces.slice(traceCount.why);
  for (const t of fresh) empty.after(traceNode(t));
  traceCount.why = snap.traces.length;
  empty.style.display = snap.traces.length ? "none" : "";
  if (fresh.length) box.scrollTo({ top: 0, behavior: "smooth" });
}

function renderLog() {
  const empty = $("#log-empty");
  for (const l of snap.log.slice(traceCount.log)) {
    empty.after(h("div", { class: "log-line" }, h("span", { class: "mono" }, clock(l.at)), l.text));
  }
  traceCount.log = snap.log.length;
  empty.style.display = snap.log.length ? "none" : "";
}

// ---- composer

function renderComposer() {
  const p = snap.people.find((x) => x.id === active);
  const as = $("#as");
  let note = "";
  if (!p.present) note = p.banned ? " · tiene ban, no está en el grupo" : " · no está en el grupo";
  else if (p.verify_left != null) note = " · sin verificar: Telegram no le deja escribir";
  else if (p.mute_left != null) note = " · en silencio";
  as.replaceChildren("Escribís como ", h("b", {}, p.name), note);
  as.classList.toggle("warn", note !== "");

  const off = !p.present;
  for (const el of document.querySelectorAll("#text, #forwarded, .send, .quick .chip")) el.disabled = off;
  $("#text").placeholder = off ? `Primero hacé entrar a ${p.name} con el botón de su tarjeta` : "Escribí un mensaje o un comando...";

  const chip = $("#reply-chip");
  chip.classList.toggle("is-on", !!replyTo);
  if (replyTo) $("#reply-text").textContent = `Respondiendo a ${replyTo.name}: ${replyTo.text}`;
}

// ------------------------------------------------------------ flotantes

let toastTimer = 0;
function toast(text, danger = false) {
  const el = $("#toast");
  el.textContent = text;
  el.classList.toggle("danger", danger);
  el.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("is-on"), Math.max(2800, text.length * 45));
}

// Tooltips propios: cualquier elemento con data-tip.
let tipTimer = 0;
let tipFor = null;
document.addEventListener("mouseover", (e) => {
  const el = e.target.closest("[data-tip]");
  if (el === tipFor) return;
  tipFor = el;
  clearTimeout(tipTimer);
  const tip = $("#tip");
  tip.classList.remove("is-on");
  if (!el) return;
  tipTimer = setTimeout(() => {
    tip.textContent = el.dataset.tip;
    const r = el.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    let x = r.left + r.width / 2 - t.width / 2;
    x = Math.max(8, Math.min(x, innerWidth - t.width - 8));
    let y = r.top - t.height - 8;
    if (y < 8) y = r.bottom + 8;
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
    tip.classList.add("is-on");
  }, 380);
});
document.addEventListener("mousedown", () => { clearTimeout(tipTimer); $("#tip").classList.remove("is-on"); });

// Fade de arriba solo cuando hay algo tapado.
for (const el of document.querySelectorAll(".scroll")) {
  const update = () => el.classList.toggle("at-top", el.scrollTop <= 1);
  el.addEventListener("scroll", update, { passive: true });
  new MutationObserver(update).observe(el, { childList: true });
  update();
}

// ------------------------------------------------------------ eventos

$("#composer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  const cmd = { op: "send", user: active, text, reply_to: replyTo?.msg_id ?? null, forwarded };
  replyTo = null;
  await send(cmd);
  input.focus();
});

$("#reply-cancel").addEventListener("click", () => { replyTo = null; renderComposer(); });

$("#forwarded").addEventListener("click", (e) => {
  forwarded = !forwarded;
  e.currentTarget.setAttribute("aria-pressed", String(forwarded));
});

document.querySelector(".quick").addEventListener("click", (e) => {
  const b = e.target.closest("[data-quick]");
  if (!b) return;
  const q = b.dataset.quick;
  if (q === "burst") send({ op: "burst", user: active });
  if (q === "album") {
    // Lo escrito en el campo va como texto del álbum, como en Telegram.
    const input = $("#text");
    const cmd = { op: "album", user: active, text: input.value.trim(), reply_to: replyTo?.msg_id ?? null, forwarded };
    input.value = "";
    replyTo = null;
    send(cmd);
  }
  if (q === "link") send({ op: "send", user: active, text: "miren esto: www.cripto-gratis.xyz", forwarded });
  if (q === "rules") send({ op: "send", user: active, text: "/reglas" });
  if (q === "staff") send({ op: "send", user: active, text: "/staff@de4dc0dex_bot" });
  if (q === "edit") {
    const last = snap.chat.findLast((m) => m.kind === "user" && m.user_id === active && !m.deleted);
    const name = snap.people.find((p) => p.id === active).name;
    if (last) send({ op: "edit", user: active, msg_id: last.msg_id, text: `${last.text} Más fotos en www.cripto-gratis.xyz`.trim() });
    else toast(`${name} no tiene mensajes en el grupo para editar.`);
  }
  if (q === "repeat") {
    // El último mensaje de esta persona que quedó en el grupo.
    const last = snap.chat.findLast((m) => m.kind === "user" && m.user_id === active && !m.deleted);
    const name = snap.people.find((p) => p.id === active).name;
    // Un álbum se repite con las mismas fotos, como al reenviarlo.
    if (last?.photos) send({ op: "album", user: active, text: last.text, photos: last.photos, forwarded });
    else if (last) send({ op: "send", user: active, text: last.text, forwarded });
    else toast(`${name} todavía no tiene mensajes en el grupo.`);
  }
});

$("#jumps").addEventListener("click", (e) => {
  const b = e.target.closest("[data-advance]");
  if (b) send({ op: "advance", seconds: Number(b.dataset.advance) });
});

$("#reset").addEventListener("click", () => send({ op: "reset" }));

$("#add-person").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("#new-name");
  const name = input.value.trim();
  if (name) send({ op: "add_user", name });
  input.value = "";
});

function moveTabBar() {
  const on = document.querySelector(".tab.is-on");
  const bar = $("#tab-bar");
  bar.style.width = `${on.offsetWidth}px`;
  bar.style.transform = `translateX(${on.offsetLeft}px)`;
  // La primera vez aparece en su lugar; de ahí en más, viaja.
  if (bar.classList.contains("placing")) requestAnimationFrame(() => bar.classList.remove("placing"));
}
for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    for (const t of document.querySelectorAll(".tab")) t.classList.toggle("is-on", t === tab);
    for (const v of document.querySelectorAll(".view")) v.classList.toggle("is-on", v.dataset.view === tab.dataset.tab);
    moveTabBar();
  });
}

// ------------------------------------------------------------ arranque y reloj

// El reloj de la cabecera y las cuentas regresivas se dibujan acá; el servidor
// solo se consulta cada dos segundos para ver si venció algo.
function frame() {
  if (snap) {
    $("#clock").textContent = clock(nowLocal());
    for (const p of snap.people) {
      const node = personNodes.get(p.id);
      if (node) syncBadges(node.querySelector(".badges"), badgesFor(p));
    }
  }
  setTimeout(frame, 250);
}

send({ op: "snapshot" }).then(() => {
  moveTabBar();
  frame();
  setInterval(() => send({ op: "tick" }).catch(() => {}), 2000);
});
