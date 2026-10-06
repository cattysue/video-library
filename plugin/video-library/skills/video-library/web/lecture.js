/* 강의 화면: 유튜브 플레이어, 전사, 목차·노트·용어집·FAQ, 복사·요청 버튼, 단축키 */
"use strict";
(() => {
  const params = new URLSearchParams(location.search);
  const lectureId = params.get("id") || "";
  const startAt = Math.max(0, Number(params.get("t")) || 0);
  const SPEEDS = [1, 1.25, 1.5, 2];
  const ASK_MESSAGE = "질문 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣고 질문을 이어 쓰세요.";
  const REQUEST_MESSAGE = "요청 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣으세요.";

  let doc = null;
  let player = null;
  let ready = false;
  let view = "orig";
  let active = -1;
  let starts = [];
  // 재생을 시작하기 전 강조 기준 시간. 링크의 초는 정수로 잘려 있으므로 그 1초 안에서 시작하는 문장을 고른다.
  let anchor = Number.isInteger(startAt) && startAt > 0 ? startAt + 0.999 : startAt;

  const firstTranslation = () => Object.keys(doc.translations)[0] || null;

  async function init() {
    if (!/^[A-Za-z0-9_-]{11}$/.test(lectureId)) return fail("강의 ID가 올바르지 않습니다.");
    try { doc = await VL.api(`/api/lectures/${encodeURIComponent(lectureId)}`); } catch (e) { return fail("강의를 불러오지 못했습니다: " + e.message); }
    starts = doc.segments.map((s) => s.start);
    document.title = `${doc.lecture.title} — 영상자료실`;
    renderHeader();
    renderTicks();
    renderSpeeds();
    renderLangSwitch();
    renderTranscript();
    renderToc();
    renderNotes();
    renderGlossary("");
    renderFaq();
    setupTabs();
    setupButtons();
    setupKeys();
    $("#find").addEventListener("input", (e) => filterTranscript(e.target.value));
    $("#glossary-find").addEventListener("input", (e) => renderGlossary(e.target.value));
    loadPlayer();
    highlightAt(now(), true);
    setInterval(tick, 250);
    VL.watchServer();
  }

  function fail(message) { $("#title").textContent = message; }

  function renderHeader() {
    const lec = doc.lecture;
    $("#title").textContent = lec.title;
    $("#badges").replaceChildren(
      VL.el("span", { class: "tag", text: VL.FIELD_LABELS[lec.field] || lec.field }),
      VL.el("span", { class: "tag lang", text: `${VL.fmtTime(lec.duration)} · 챕터 ${doc.chapters.length}` }));
  }

  /* ---- 플레이어 ---- */
  function loadPlayer() {
    window.onYouTubeIframeAPIReady = () => {
      player = new YT.Player("player", {
        videoId: doc.lecture.video_id,
        playerVars: { playsinline: 1, rel: 0, start: Math.floor(startAt), origin: location.origin },
        events: {
          onReady: () => { ready = true; updateClock(); },
          onStateChange: (e) => { if (e.data === 1) anchor = null; },
          onError: (e) => VL.toast(`영상을 재생할 수 없습니다(유튜브 오류 ${e.data}).`),
        },
      });
    };
    document.head.append(VL.el("script", { src: "https://www.youtube.com/iframe_api" }));
  }

  const now = () => (anchor !== null ? anchor : (ready && player.getCurrentTime ? player.getCurrentTime() : startAt));
  const playing = () => ready && player.getPlayerState && player.getPlayerState() === 1;

  function seek(t, play = true) {
    const target = Math.max(0, Math.min(t, doc.lecture.duration));
    anchor = ready && play ? null : target;
    if (ready) {
      player.seekTo(target, true);
      if (play) player.playVideo();
    }
    highlightAt(target, true);
    updateClock(target);
  }

  function tick() {
    if (!ready) return;
    updateClock();
    highlightAt(now(), false);
  }

  function updateClock(at) {
    const t = at === undefined ? now() : at;
    const total = (ready && player.getDuration && player.getDuration()) || doc.lecture.duration;
    $("#clock").textContent = `${VL.fmtTime(t)} / ${VL.fmtTime(total)}`;
    const bar = $("#ticks").querySelector(".progress");
    if (bar) bar.style.width = `${Math.min(100, (t / total) * 100)}%`;
  }

  function renderTicks() {
    const total = doc.lecture.duration;
    const box = $("#ticks");
    box.replaceChildren(VL.el("div", { class: "progress" }),
      ...doc.chapters.slice(1).map((ch) => {
        const tick = VL.el("span", { class: "tick", title: ch.title });
        tick.style.left = `${(ch.start / total) * 100}%`;
        return tick;
      }));
    box.addEventListener("click", (e) => {
      const rect = box.getBoundingClientRect();
      seek(((e.clientX - rect.left) / rect.width) * total);
    });
  }

  function renderSpeeds() {
    $("#speeds").replaceChildren(...SPEEDS.map((rate) => VL.el("button", {
      type: "button", class: "btn small" + (rate === 1 ? " active" : ""),
      onclick: (e) => {
        if (ready) player.setPlaybackRate(rate);
        for (const b of $("#speeds").children) b.classList.toggle("active", b === e.currentTarget);
      },
    }, `${rate}x`)));
  }

  /* ---- 전사 ---- */
  function renderLangSwitch() {
    const tr = firstTranslation();
    if (!tr) return;
    const orig = doc.lecture.language.toUpperCase();
    const options = [["orig", `원문(${orig})`], [tr, `번역(${tr.toUpperCase()})`], ["both", "나란히"]];
    const box = $("#lang-switch");
    box.hidden = false;
    box.replaceChildren(...options.map(([key, label]) => VL.el("button", {
      type: "button", class: key === view ? "active" : "",
      onclick: (e) => {
        view = key;
        for (const b of box.children) b.classList.toggle("active", b === e.currentTarget);
        renderTranscript();
        filterTranscript($("#find").value);
      },
    }, label)));
  }

  function linesFor(key) {
    if (key === "orig" || !doc.translations[key]) return doc.segments.map((s) => s.text);
    return doc.translations[key].map((it) => it.text);
  }

  function renderTranscript() {
    const orig = linesFor("orig");
    const tr = firstTranslation();
    const shown = view === "both" ? orig : linesFor(view);
    const second = view === "both" && tr ? linesFor(tr) : null;
    $("#transcript").replaceChildren(...doc.segments.map((s, i) => VL.el("li", {
      "data-i": i, onclick: () => seek(s.start),
    },
    VL.el("span", { class: "time", text: VL.fmtTime(s.start) }),
    VL.el("span", {}, shown[i], second ? VL.el("span", { class: "tr", text: second[i] }) : null))));
    active = -1;
    highlightAt(now(), true);
    $("#count").textContent = `문장 ${doc.segments.length}개`;
  }

  function indexAt(t) {
    let lo = 0;
    let hi = starts.length - 1;
    let found = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (starts[mid] <= t + 0.01) { found = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return found;
  }

  function highlightAt(t, force) {
    const i = indexAt(t);
    if (i === active && !force) return;
    const list = $("#transcript");
    if (active >= 0 && list.children[active]) list.children[active].classList.remove("active");
    active = i;
    const li = list.children[i];
    if (!li) return;
    li.classList.add("active");
    if (force || playing()) list.scrollTop = li.offsetTop - list.offsetTop - list.clientHeight / 3;
  }

  function filterTranscript(query) {
    const q = query.trim().toLowerCase();
    let shown = 0;
    for (const li of $("#transcript").children) {
      const match = !q || li.textContent.toLowerCase().includes(q);
      li.hidden = !match;
      if (match) shown += 1;
    }
    $("#count").textContent = q ? `${shown}개 일치` : `문장 ${doc.segments.length}개`;
  }

  function copyTranscript(timed) {
    const orig = linesFor("orig");
    const tr = firstTranslation();
    const rows = doc.segments.map((s, i) => {
      const parts = view === "both" ? [orig[i], tr ? linesFor(tr)[i] : null].filter(Boolean) : [linesFor(view)[i]];
      const text = parts.join("\n");
      return timed ? `[${VL.fmtTime(s.start)}] ${text}` : text;
    });
    VL.copy(rows.join("\n"), timed ? "시간 포함 전사를 복사했습니다." : "전사를 복사했습니다.");
  }

  /* ---- 오른쪽 탭 ---- */
  function chapterButton(ch, child) {
    const minutes = Math.max(1, Math.round((ch.end - ch.start) / 60));
    return VL.el("button", { type: "button", class: "toc-item" + (child ? " toc-child" : ""), onclick: () => seek(ch.start) },
      VL.el("span", { text: `${ch.id}. ${ch.title}` }),
      VL.el("span", { class: "toc-time", text: `${VL.fmtTime(ch.start)} · ${minutes}분` }));
  }

  function renderToc() {
    $("#tab-toc").replaceChildren(...doc.chapters.flatMap((ch) => [chapterButton(ch, false),
      ...(ch.children || []).map((c) => chapterButton(c, true))]));
  }

  const timeButton = (t) => VL.el("button", { type: "button", class: "link-btn", onclick: () => seek(t) }, VL.fmtTime(t));
  const startOf = (idx) => (doc.segments[idx - 1] ? doc.segments[idx - 1].start : 0);

  function renderNotes() {
    const blocks = [VL.el("h2", { text: "챕터 요약" })];
    for (const ch of doc.chapters) {
      blocks.push(VL.el("h3", {}, `${ch.id}. ${ch.title} `, timeButton(ch.start)), VL.el("p", { text: ch.summary }));
      for (const c of ch.children || []) {
        blocks.push(VL.el("div", { class: "child" }, VL.el("h4", { text: `${c.id} ${c.title}` }), VL.el("p", { text: c.summary })));
      }
    }
    if (doc.mentions.length) {
      blocks.push(VL.el("h2", { text: "영상에서 언급된 자료" }), VL.el("ul", {}, ...doc.mentions.map((m) => VL.el("li", {},
        m.url ? VL.el("a", { href: m.url, target: "_blank", rel: "noopener noreferrer", text: m.text }) : m.text,
        " ", timeButton(startOf(m.idx))))));
    }
    $("#tab-notes").replaceChildren(...blocks);
  }

  function renderGlossary(query) {
    const q = query.trim().toLowerCase();
    const items = doc.glossary.filter((g) => !q || `${g.term} ${g.definition}`.toLowerCase().includes(q));
    $("#glossary-list").replaceChildren(...(items.length ? items.map((g) => VL.el("div", { class: "gloss" },
      VL.el("div", { class: "gloss-head" }, VL.el("span", { class: "gloss-term", text: g.term }), timeButton(startOf(g.idx))),
      VL.el("div", { text: g.definition }),
      g.analogy ? VL.el("div", { class: "gloss-analogy", text: g.analogy }) : null,
      g.claim_note ? VL.el("div", { class: "gloss-claim", text: `영상 속 주장 · ${g.claim_note}` }) : null))
      : [VL.el("p", { class: "muted", text: doc.glossary.length ? "일치하는 용어가 없습니다." : "용어집이 없습니다." })]));
  }

  function renderFaq() {
    $("#tab-faq").replaceChildren(...(doc.faq.length ? doc.faq.map((f) => VL.el("div", { class: "faq" },
      VL.el("div", { class: "faq-q", text: `Q. ${f.question}` }),
      VL.el("div", { text: f.answer }),
      VL.el("div", { class: "evidence" }, ...f.evidence.map((idx) => VL.el("button", {
        type: "button", class: "btn small", onclick: () => seek(startOf(idx)),
      }, `근거 장면 ${VL.fmtTime(startOf(idx))}`)))))
      : [VL.el("p", { class: "muted", text: "FAQ가 없습니다." })]));
  }

  function setupTabs() {
    const buttons = document.querySelectorAll(".tabs [data-tab]");
    for (const button of buttons) {
      button.addEventListener("click", () => {
        for (const b of buttons) {
          const on = b === button;
          b.setAttribute("aria-selected", String(on));
          document.getElementById(`tab-${b.dataset.tab}`).hidden = !on;
        }
      });
    }
  }

  async function setupButtons() {
    $("#copy-plain").addEventListener("click", () => copyTranscript(false));
    $("#copy-timed").addEventListener("click", () => copyTranscript(true));
    $("#ask").addEventListener("click", () =>
      VL.copy(`video-library 강의 「${doc.lecture.title}」(${lectureId})에 대해 질문: `, ASK_MESSAGE));
    const needsEnglish = doc.lecture.language === "ko" && !doc.translations.en;
    $("#request-en").hidden = !needsEnglish;
    $("#request-en").addEventListener("click", () => VL.copy(`video-library 번역 ${lectureId}`, REQUEST_MESSAGE));
    const info = await VL.info();
    const visitor = info.mode !== "pc" && !info.admin; // 공개 서버(hosted) 손님: AI 도구용 버튼은 의미가 없다
    if (visitor) {
      $("#ask").hidden = true;
      $("#request-en").hidden = true;
    }
  }

  function setupKeys() {
    document.addEventListener("keydown", (e) => {
      if (e.target.closest("input, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === "j") seek(now() - 10);
      else if (key === "l") seek(now() + 10);
      else if (key === "k") { if (ready) (playing() ? player.pauseVideo() : player.playVideo()); }
      else if (e.key === "ArrowLeft") seek(now() - 5);
      else if (e.key === "ArrowRight") seek(now() + 5);
      else if (/^[1-9]$/.test(e.key) && doc.chapters[Number(e.key) - 1]) seek(doc.chapters[Number(e.key) - 1].start);
      else return;
      e.preventDefault();
    });
  }

  init();
})();
