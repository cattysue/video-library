/* 목록 화면: 강의 카드, 분야 필터, 통합 검색, 진행 카드 */
"use strict";
(() => {
  const STEP_LABELS = {
    fetch: "자막 받기", preprocess: "정리", chunk: "나누기", context: "맥락 파악", correct: "교정·교열",
    merge: "합치기", outline: "목차·요약", glossary: "용어집", translate: "번역", faq: "FAQ",
    assemble: "조립", upload: "업로드",
  };
  const STEP_MARKS = { done: "✓", running: "●", failed: "✕", skipped: "–", pending: "○" };
  const STATUS_LABELS = { running: "진행 중", done: "완료", failed: "실패" };
  const WHERE_LABELS = { title: "제목", chapter: "목차", glossary: "용어집", segment: "전사", translation: "번역" };
  const DONE_HIDE_MS = 60000;
  const DISMISS_KEY = "vl.dismissedJobs";

  const state = { lectures: [], field: "", query: "", dismissed: loadDismissed(), running: new Set(), hosted: false, admin: false };

  function loadDismissed() {
    try { return new Set(JSON.parse(localStorage.getItem(DISMISS_KEY) || "[]")); } catch (e) { return new Set(); }
  }
  function saveDismissed() {
    try { localStorage.setItem(DISMISS_KEY, JSON.stringify([...state.dismissed].slice(-50))); } catch (e) { /* 저장 불가 */ }
  }

  function renderFilters() {
    const options = [["", "전체"], ...Object.entries(VL.FIELD_LABELS)];
    $("#filters").replaceChildren(...options.map(([key, label]) => VL.el("button", {
      type: "button", class: `chip pebble field-${key || "all"}` + (state.field === key ? " active" : ""), "aria-pressed": String(state.field === key),
      onclick: () => { state.field = key; renderFilters(); refresh(); },
    }, label)));
  }

  function lectureCard(item) {
    const href = `/lecture?id=${encodeURIComponent(item.id)}`;
    const pair = VL.langPair(item.language, item.translations);
    return VL.el("article", { class: "card" },
      VL.el("a", { href, class: "thumb", "aria-hidden": "true", tabindex: "-1" },
        VL.el("img", { src: item.thumbnail_url, alt: "", loading: "lazy" })),
      VL.el("div", { class: "card-body" },
        VL.el("a", { href, class: "card-title", text: item.title }),
        VL.el("div", { class: "meta" },
          VL.el("span", { class: "tag", text: VL.FIELD_LABELS[item.field] || item.field }),
          VL.el("span", { text: `${VL.fmtTime(item.duration)} · 챕터 ${item.chapter_count} · ${VL.fmtDate(item.processed_at)}` }),
          pair ? VL.el("span", { class: "tag lang", text: pair }) : null)),
      VL.el("div", { class: "card-actions" },
        state.admin ? adminButtons(item) : null,
        VL.el("a", { href, class: `pebble view field-${VL.FIELD_LABELS[item.field] ? item.field : "other"}` }, "보기")));
  }

  function adminButtons(item) {
    return [
      VL.el("button", { type: "button", class: "btn small" + (item.public ? " public-on" : ""),
        "aria-pressed": String(!!item.public),
        onclick: () => togglePublic(item) }, item.public ? "공개 중" : "비공개"),
      VL.el("button", { type: "button", class: "btn small ghost danger", onclick: () => removeLecture(item) }, "삭제"),
    ];
  }

  async function togglePublic(item) {
    try {
      await VL.send("PATCH", `/api/lectures/${encodeURIComponent(item.id)}`, { public: !item.public });
      VL.toast(item.public ? "비공개로 바꿨습니다." : "공개했습니다. 로그인하지 않은 사람도 볼 수 있습니다.");
      loadLectures();
    } catch (e) { VL.toast("바꾸지 못했습니다: " + e.message); }
  }

  async function removeLecture(item) {
    if (!confirm(`「${item.title}」을(를) Railway 서버에서 삭제할까요? 내 PC 영상자료실의 원본은 그대로 남습니다.`)) return;
    try {
      await VL.send("DELETE", `/api/lectures/${encodeURIComponent(item.id)}`);
      VL.toast("삭제했습니다.");
      loadLectures();
    } catch (e) { VL.toast("삭제하지 못했습니다: " + e.message); }
  }

  function renderList() {
    const items = state.lectures.filter((x) => !state.field || x.field === state.field);
    $("#list").replaceChildren(...items.map(lectureCard));
    $("#empty").hidden = state.lectures.length > 0 || state.query.length > 0;
  }

  async function loadLectures() {
    try { state.lectures = await VL.api("/api/lectures"); } catch (e) { VL.toast("목록을 불러오지 못했습니다: " + e.message); }
    renderList();
  }

  let searchTimer = null;
  function onSearchInput(event) {
    clearTimeout(searchTimer);
    state.query = event.target.value.trim();
    searchTimer = setTimeout(refresh, 250);
  }

  async function refresh() {
    const searching = state.query.length > 0;
    $("#list").hidden = searching;
    $("#results").hidden = !searching;
    if (!searching) { renderList(); return; }
    $("#empty").hidden = true;
    const params = new URLSearchParams({ q: state.query });
    if (state.field) params.set("field", state.field);
    const asked = state.query;
    let data;
    try { data = await VL.api("/api/search?" + params); } catch (e) { VL.toast("검색하지 못했습니다: " + e.message); return; }
    if (asked !== state.query) return; // 늦게 도착한 이전 검색 결과는 버린다
    renderResults(data);
  }

  function renderResults(data) {
    if (!data.results.length) {
      $("#results").replaceChildren(VL.el("p", { class: "empty", text: `"${data.query}" 검색 결과가 없습니다.` }));
      return;
    }
    $("#results").replaceChildren(...data.results.map((r) => VL.el("article", { class: "result" },
      VL.el("h2", { class: "result-title" }, VL.el("a", { href: `/lecture?id=${encodeURIComponent(r.id)}`, text: r.title })),
      VL.el("ul", { class: "hits" }, ...r.hits.map((h) => VL.el("li", {},
        VL.el("a", { href: `/lecture?id=${encodeURIComponent(r.id)}&t=${Math.floor(h.start)}` },
          VL.el("span", { class: "time", text: VL.fmtTime(h.start) }),
          VL.el("span", { class: "where", text: WHERE_LABELS[h.where] + (h.lang ? ` ${h.lang.toUpperCase()}` : "") }),
          VL.el("span", {}, ...VL.highlight(h.text, data.query)))))))));
  }

  const uploadFailed = (job) => job.status === "done" && !!job.steps && job.steps.upload === "failed";

  // PC 는 완료면 강의가 있다. Railway 는 업로드가 실패했을 수 있으니 목록에 있을 때만(재감수 N3)
  const canView = (job) => job.status === "done" && (!state.hosted || state.lectures.some((l) => l.id === job.lecture_id));

  function visible(job) {
    if (state.dismissed.has(job.job_id)) return false;
    if (uploadFailed(job)) return true; // 닫을 때까지 남긴다
    if (job.status === "done") return Date.now() - Date.parse(job.updated_at) < DONE_HIDE_MS;
    return true;
  }

  function jobCard(job) {
    const end = job.status === "running" ? Date.now() : Date.parse(job.updated_at);
    const elapsed = VL.fmtElapsed(end - Date.parse(job.started_at));
    const status = `${STATUS_LABELS[job.status] || job.status} · ${elapsed}${job.detail ? ` · ${job.detail}` : ""}`;
    const steps = Object.keys(STEP_LABELS).map((key) => {
      const s = (job.steps && job.steps[key]) || "pending";
      return VL.el("span", { class: `step ${s}` }, `${STEP_MARKS[s] || "○"} ${STEP_LABELS[key]}`);
    });
    return VL.el("article", { class: "job" + (job.status === "failed" ? " failed" : "") + (uploadFailed(job) ? " warn" : "") },
      VL.el("div", { class: "job-head" },
        VL.el("span", { class: "job-title", text: job.title || job.lecture_id }),
        VL.el("span", { class: "job-status", text: status }),
        canView(job) ? VL.el("a", { class: "btn small", href: `/lecture?id=${encodeURIComponent(job.lecture_id)}` }, "보기") : null,
        VL.el("button", { class: "btn small ghost", type: "button", "aria-label": "진행 카드 닫기",
          onclick: () => { state.dismissed.add(job.job_id); saveDismissed(); pollJobs(); } }, "×")),
      VL.el("div", { class: "steps" }, ...steps),
      job.status === "failed" ? VL.el("div", { class: "job-error", text: `${job.error || "실패"} — AI 도구 대화창에서 다시 실행하세요.` }) : null,
      uploadFailed(job) ? VL.el("div", { class: "job-warn", text: `${job.error || "업로드 실패"} — PC에는 저장됐고 업로드만 실패했습니다. 대화창에 "video-library 업로드 ${job.lecture_id}"를 입력하면 다시 올립니다.` }) : null);
  }

  async function pollJobs() {
    if (document.hidden) return; // 숨겨진 탭은 조회하지 않는다(미니 서버가 1시간 뒤 스스로 꺼질 수 있게)
    if (state.hosted && !state.admin) return;
    let jobs = [];
    try { jobs = await VL.api("/api/jobs"); } catch (e) { return; }
    let finished = false;
    for (const job of jobs) {
      if (job.status === "running") state.running.add(job.job_id);
      else if (state.running.delete(job.job_id) && job.status === "done") finished = true;
    }
    $("#jobs").replaceChildren(...jobs.filter(visible).map(jobCard));
    if (finished) loadLectures();
  }

  function setupAdmin() {
    const btn = $("#admin-btn");
    btn.hidden = false;
    btn.textContent = state.admin ? "로그아웃" : "관리자";
    btn.addEventListener("click", async () => {
      if (!state.admin) { $("#login").hidden = !$("#login").hidden; $("#password").focus(); return; }
      try { await VL.send("POST", "/api/logout"); } catch (e) { /* 이미 끝난 세션 */ }
      location.reload();
    });
    $("#login").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await VL.send("POST", "/api/login", { password: $("#password").value });
        location.reload();
      } catch (e) {
        $("#password").value = "";
        VL.toast(e.status === 429 ? "로그인 시도가 너무 많습니다. 15분 뒤 다시 시도하세요." : "로그인하지 못했습니다: " + e.message);
      }
    });
    if (!state.admin) $("#empty").textContent = "아직 공개된 강의가 없습니다.";
  }

  async function start() {
    const info = await VL.info();
    state.hosted = info.mode !== "pc"; // 확인 실패(unknown)도 공개 서버처럼 조심스럽게
    state.admin = !!info.admin;
    if (info.mode === "hosted") setupAdmin();
    renderFilters();
    loadLectures();
    pollJobs();
    setInterval(pollJobs, 2000);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) return;
      pollJobs();
      loadLectures(); // 숨긴 동안 끝난 강의도 보이게(재감수 N1)
    });
    VL.watchServer();
    $("#search").addEventListener("input", onSearchInput);
  }

  start();
})();
