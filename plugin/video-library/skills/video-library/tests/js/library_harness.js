// 목록 화면(library.js)을 가짜 화면·가짜 서버로 실제 실행해 보는 동작 시험(Node). pytest 가 부른다.
// 사용: node library_harness.js <시나리오>  → 결과 JSON 한 줄
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scenario = process.argv[2];
const els = {};
function makeEl() {
  return {
    hidden: false, textContent: "", value: "", children: [], listeners: {},
    replaceChildren(...c) { this.children = c; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    focus() {},
  };
}
const $ = (sel) => (els[sel] = els[sel] || makeEl());
const docListeners = {};
const document = { hidden: false, addEventListener(t, f) { (docListeners[t] = docListeners[t] || []).push(f); } };
const calls = [];
let responses = {};
let info = { mode: "pc" };
let interval = null;
const VL = {
  FIELD_LABELS: { dev: "개발", other: "기타" },
  el: (tag, attrs = {}, ...children) => ({ tag, attrs, children: children.flat().filter((x) => x !== null && x !== undefined && x !== false) }),
  api: async (p) => { calls.push(p); return JSON.parse(JSON.stringify(responses[p] === undefined ? [] : responses[p])); },
  info: async () => info, send: async () => ({}), toast() {}, watchServer() {},
  langPair: () => "", fmtTime: () => "0:00:00", fmtDate: () => "", fmtElapsed: () => "0초", highlight: (t) => [t],
};
const sandbox = {
  $, document, VL, console,
  localStorage: { getItem: () => null, setItem() {} },
  location: { reload() {} },
  setInterval: (f) => { interval = f; return 1; }, setTimeout: (f) => { f(); return 1; }, clearTimeout() {},
  Date, JSON, Set, Object, Promise, encodeURIComponent, URLSearchParams,
};
const flush = async () => { for (let i = 0; i < 10; i += 1) await new Promise((r) => setImmediate(r)); };
const iso = (msAgo) => new Date(Date.now() - msAgo).toISOString();
const job = (over) => Object.assign({ job_id: "AbCdEfGhIjK-1008-1200", lecture_id: "AbCdEfGhIjK", title: "시험 강의",
  status: "done", started_at: iso(300000), updated_at: iso(120000), steps: { assemble: "done", upload: "done" },
  detail: "", error: null }, over);
const lecture = { id: "AbCdEfGhIjK", title: "시험 강의", field: "dev", duration: 60, chapter_count: 1,
  processed_at: "2026-10-08T12:00:00+09:00", thumbnail_url: "", language: "ko", translations: [] };
function hasViewLink(node) {
  if (!node || typeof node !== "object") return false;
  if (node.tag === "a" && node.children.includes("보기")) return true;
  return (node.children || []).some(hasViewLink);
}

async function run() {
  const code = fs.readFileSync(path.join(__dirname, "..", "..", "web", "library.js"), "utf8");
  if (scenario === "lectures-after-hidden") {
    responses = { "/api/lectures": [], "/api/jobs": [] };
    vm.runInNewContext(code, sandbox);
    await flush();
    document.hidden = true; // 다른 탭으로 감
    responses = { "/api/lectures": [lecture], "/api/jobs": [job({})] }; // 숨긴 동안 처리 시작·완료
    const before = calls.length;
    if (interval) interval();
    await flush();
    const hiddenCalls = calls.length - before;
    document.hidden = false; // 돌아옴
    (docListeners.visibilitychange || []).forEach((f) => f());
    await flush();
    console.log(JSON.stringify({ hiddenCalls, cards: $("#list").children.length }));
  } else if (scenario === "view-link") {
    info = process.argv[3] === "hosted" ? { mode: "hosted", admin: true } : { mode: "pc" };
    responses = { "/api/lectures": [], "/api/jobs": [job({ steps: { assemble: "done", upload: "failed" }, error: "업로드 실패(401)" })] };
    vm.runInNewContext(code, sandbox);
    await flush();
    console.log(JSON.stringify({ hasView: $("#jobs").children.some(hasViewLink), cards: $("#jobs").children.length }));
  } else {
    throw new Error("알 수 없는 시나리오: " + scenario);
  }
}
run().catch((e) => { console.error(e); process.exit(1); });
