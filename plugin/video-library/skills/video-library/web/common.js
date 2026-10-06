/* 영상자료실 화면 공통 도구. 데이터는 언제나 textContent 로만 넣는다(AI가 만든 글에 HTML 이 섞여도 글자로 보이게). */
"use strict";
const $ = (selector) => document.querySelector(selector);

const VL = (() => {
  const FIELD_LABELS = { dev: "개발", finance: "금융·투자", science: "과학기술", medical: "의학·보건", other: "기타" };

  const SERVER_DOWN_MSG = "미니 서버가 꺼졌습니다 — 영상자료실 폴더의 「영상자료실 열기」를 더블클릭하세요.";
  const DOWN_AFTER = 2; // 연속 실패 횟수
  let failures = 0;

  const HOSTED_DOWN_MSG = "서버에 연결하지 못했습니다. 잠시 뒤 새로고침하세요.";
  let knownMode = null; // /api/health 로 알게 된 서버 종류

  function serverStatus(ok) {
    failures = ok ? 0 : failures + 1;
    let banner = document.getElementById("server-down");
    if (failures >= DOWN_AFTER && !banner) {
      const text = knownMode === "pc" ? SERVER_DOWN_MSG : HOSTED_DOWN_MSG;
      banner = el("div", { id: "server-down", class: "server-down", role: "alert", text });
      document.body.prepend(banner);
    } else if (ok && banner) {
      banner.remove();
    }
  }

  async function api(path) {
    let resp;
    try {
      resp = await fetch(path, { cache: "no-store" });
    } catch (e) {
      serverStatus(false);
      throw new Error("서버에 연결하지 못했습니다");
    }
    serverStatus(true);
    if (!resp.ok) {
      let message = resp.statusText;
      try { message = (await resp.json()).error || message; } catch (e) { /* 본문 없음 */ }
      throw new Error(message);
    }
    return resp.json();
  }

  let infoPromise = null;
  function info() {
    if (!infoPromise) {
      infoPromise = api("/api/health").then((data) => { knownMode = data.mode; return data; }).catch(() => {
        infoPromise = null; // 다음에 다시 확인한다
        return { mode: "unknown" }; // 모르면 PC 로 넘겨짚지 않는다(손님에게 PC 기능을 보이지 않게)
      });
    }
    return infoPromise;
  }

  async function send(method, path, body) {
    let resp;
    try {
      resp = await fetch(path, {
        method, cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Requested-With": "video-library" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      serverStatus(false);
      throw new Error("서버에 연결하지 못했습니다");
    }
    serverStatus(true);
    let data = {};
    try { data = await resp.json(); } catch (e) { /* 본문 없음 */ }
    if (!resp.ok) {
      const err = new Error(data.error || resp.statusText);
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  async function ping() {
    try { await api("/api/health"); } catch (e) {
      if (failures > 0 && failures < DOWN_AFTER) setTimeout(ping, 3000); // 한 번 더 확인한 뒤 안내
    }
  }

  // 화면이 보이는 동안 5분마다, 그리고 탭으로 돌아올 때마다 서버가 살아 있는지 확인한다
  function watchServer() {
    setInterval(() => { if (!document.hidden) ping(); }, 5 * 60 * 1000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) ping(); });
  }

  const pad = (n) => String(n).padStart(2, "0");

  function fmtTime(sec) {
    const s = Math.max(0, Math.floor(Number(sec) || 0));
    return `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
  }

  function fmtDate(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}.`;
  }

  function fmtElapsed(ms) {
    const s = Math.max(0, Math.round(ms / 1000));
    return s >= 60 ? `${Math.floor(s / 60)}분 ${s % 60}초` : `${s}초`;
  }

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : String(value));
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function highlight(text, query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) return [text];
    const lower = text.toLowerCase();
    const parts = [];
    let from = 0;
    for (let at = lower.indexOf(q); at !== -1; at = lower.indexOf(q, from)) {
      if (at > from) parts.push(text.slice(from, at));
      parts.push(el("mark", { text: text.slice(at, at + q.length) }));
      from = at + q.length;
    }
    parts.push(text.slice(from));
    return parts;
  }

  let toastTimer = null;
  function toast(message) {
    const box = document.getElementById("toast");
    if (!box) return;
    box.textContent = message;
    box.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { box.hidden = true; }, 4000);
  }

  async function copy(text, message) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const area = el("textarea", { readonly: true });
      area.value = text;
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    toast(message);
  }

  function langPair(language, translations) {
    const langs = (translations || []).filter((l) => l !== language);
    return langs.length ? `${language.toUpperCase()}→${langs.map((l) => l.toUpperCase()).join("·")}` : "";
  }

  return { FIELD_LABELS, api, info, send, watchServer, fmtTime, fmtDate, fmtElapsed, el, highlight, toast, copy, langPair };
})();
