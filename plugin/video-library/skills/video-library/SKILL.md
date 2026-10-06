---
name: video-library
description: '유튜브 영상 링크 하나로 자막을 교정·교열하고 목차·요약·용어집·번역·FAQ를 만들어 내 PC의 영상자료실(문서/영상자료실)에 쌓는다. Claude Code에서는 /video-library:video-library <링크>, Codex에서는 $video-library <링크>로 호출하고, "video-library로 이 영상 정리해줘 <링크>"처럼 평문으로 요청해도 된다. "video-library 번역 <영상ID>"(한국어 강의의 영어 번역 추가) 요청도 이 스킬로 처리한다. 영상자료실 화면 열기("영상자료실 열어줘", "video-library 열기")와, 영상자료실에 쌓인 강의 내용 질문("video-library 강의 「제목」(<ID>)에 대해 질문: …")도 이 스킬로 처리한다. 내 Railway 서버로 강의 올리기("video-library 업로드 <ID>")와 Railway 연결 안내도 이 스킬로 처리한다.'
---

# video-library

유튜브 영상의 자막을 받아 **기계 단계는 동봉된 파이썬 스크립트(`vl.py`)**, **판단 단계는 이 문서의 브리프**로 처리한다. 판단 결과는 `vl.py check`를 통과해야만 다음 단계로 간다.

## 규칙
- `$SKILL` = 이 SKILL.md가 있는 폴더의 절대경로. `$PY` = 0단계 `doctor`가 출력한 파이썬 경로(보통 Windows는 `python`, 그 밖은 `python3`).
- 모든 명령은 `"$PY" "$SKILL/scripts/vl.py" <명령> …` 형식이다. 이하 `vl.py <명령>`으로 줄여 쓴다.
- Windows PowerShell(Codex 등)에서는 명령 앞에 `&`를 붙이고, 한글 출력이 깨지지 않게 같은 줄 맨 앞에 `[Console]::OutputEncoding=[Text.UTF8Encoding]::new();`를 넣는다. 예: `[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); & "$PY" "$SKILL/scripts/vl.py" doctor`. Git Bash·macOS·Linux 셸에서는 그대로 쓴다.
- 결과물은 영상자료실(기본 `문서/영상자료실`, 환경변수 `VL_HOME`으로 변경)에 쌓인다. `fetch`가 출력한 `work_dir`(= `<영상자료실>/lectures/<ID>.tmp`)을 이하 `<W>`, `video_id`를 `<ID>`라 한다.
- 화면: `vl.py open`이 영상자료실 화면을 브라우저로 연다. 화면 파일을 `<영상자료실>/app/`에 설치하고, 내 PC 전용 미니 서버(`vl.py serve`)가 꺼져 있으면 백그라운드로 켠다(1시간 쓰지 않으면 스스로 꺼짐). 출력 JSON의 `url`(예: `http://127.0.0.1:8765`)을 이하 `<URL>`이라 한다.
- 옵션: `--translate-en`(한국어 영상의 전사를 영어로도 번역), `--lang xx`(영상 언어를 직접 지정), `--no-upload`(Railway 업로드 설정이 있어도 이번에는 올리지 않음).
- 사용자에게 업로드 토큰·관리자 비밀번호를 묻거나 출력하지 않는다. `vl.py connect`는 사용자가 직접 실행한다. 설치 명령은 사용자 승인 후에만 실행한다.
- 판단 단계는 시작할 때 `vl.py progress --video <ID> --step <단계> --status running`, 끝나면 `--status done`을 보낸다(목록 화면의 진행 카드용).
- 브리프를 에이전트에게 줄 때는 `<W>`·`<ID>`·`NN`(조각 번호 두 자리)·`$PY`·`$SKILL`을 실제 값으로 바꿔 그대로 전달한다.
- 검사 불합격이면 오류 메시지를 브리프 끝에 붙여 **1회** 다시 시킨다. 그래도 불합격이면:
  - 핵심 단계(context·correct·outline)는 멈추고 원인을 사용자에게 알린다. 멈추기 전에 `vl.py progress --video <ID> --step <단계> --status failed --error "<원인 한 줄>"`로 진행 카드에 실패를 남긴다.
  - 선택 단계(glossary·translate·faq)는 그 결과 파일을 지우고 `--status skipped`로 보고한 뒤 계속한다.
- 기계 단계가 `오류: …`로 실패하면 그 메시지를 사용자에게 그대로 전하고, 원인을 고친 뒤 **그 단계부터** 다시 실행한다.

## 단계
0. **점검·열기** — `vl.py doctor`. `✗`(필수) 항목이 있으면 출력된 설치 명령을 사용자에게 보여주고 승인을 받아 실행한 뒤 다시 점검한다. `△`(권장)는 알리고 진행한다. 점검을 통과하면 `vl.py open`으로 목록 화면을 열어 둔다(진행 카드로 단계가 보인다).
1. **자막 받기** — `vl.py fetch "<링크>" [--translate-en] [--lang xx] [--no-upload]`. 출력 JSON의 `video_id`, `work_dir`, `language`, `translate`, `long`, `upload`을 기억한다. `long`이 true(1시간 초과)면 처리 시간이 길고 구독 사용량이 많이 든다는 점을 알리고 계속할지 묻는다.
2. **정리** — `vl.py preprocess --video <ID>`
3. **나누기** — `vl.py chunk --video <ID>` → `<W>/build/chunks/manifest.json`에 조각 목록
4. **맥락 파악(판단)** — `vl.py progress --video <ID> --step context` → [맥락 브리프] 수행(에이전트 1개 또는 직접) → `vl.py check --video <ID> --kind context` → `--status done`
5. **교정·교열(판단)** — `vl.py progress --video <ID> --step correct` → 조각마다 [교정 브리프]. Claude Code에서는 서브에이전트를 최대 8개씩 병렬로 쓴다. Codex에서는 병렬 에이전트를 쓸 수 있으면 최대 8개씩, 아니면 차례로 처리한다. 조각마다 `vl.py check --video <ID> --kind edits --chunk NN`. 묶음이 끝날 때마다 `vl.py progress --video <ID> --step correct --detail "완료/전체"` → 모두 끝나면 `--status done`
6. **합치기** — `vl.py merge --video <ID> --kind edits` (불합격 조각이 있으면 그 조각만 5단계를 다시)
7. **목차·요약(판단)** — `vl.py progress --video <ID> --step outline` → [목차 브리프] → `vl.py check --video <ID> --kind outline` → `--status done`
8. **용어집(판단)** — `vl.py progress --video <ID> --step glossary` → [용어집 브리프] → `vl.py check --video <ID> --kind glossary` → `--status done`
9. **번역(판단)** — fetch 출력의 `translate`가 true일 때만. 대상 언어 L = 원문이 한국어가 아니면 `ko`, `--translate-en`이면 `en`. `vl.py progress --video <ID> --step translate` → 조각마다 [번역 브리프](5단계처럼 병렬) → 조각마다 `vl.py check --video <ID> --kind translation --lang L --chunk NN` → `vl.py merge --video <ID> --kind translation --lang L`
10. **FAQ(판단)** — `vl.py progress --video <ID> --step faq` → [FAQ 브리프] → `vl.py check --video <ID> --kind faq` → `--status done`
11. **조립** — `vl.py assemble --video <ID>` → 영상자료실에 반영된다. 출력의 `lecture_dir`와 `skipped`를 사용자에게 알린다. 빠진 단계가 있으면 나중에 다시 요청할 수 있다고 안내한다. `vl.py open --no-browser`로 미니 서버를 확인한 뒤 강의 화면 주소 `<URL>/lecture?id=<ID>`도 알려 준다.
12. **업로드** — fetch 출력의 `upload`가 true일 때만 `vl.py upload --video <ID>`. 성공하면 출력의 `url`을 알려 주고, **새 강의는 비공개**라 남에게 보이려면 Railway 화면에서 관리자로 로그인해 [비공개]를 눌러 공개로 바꿔야 한다고 안내한다. 실패해도 PC 영상자료실의 결과는 그대로이며, 원인을 고친 뒤 같은 명령으로 다시 올릴 수 있다고 안내한다.

## 나중 요청: 영상자료실 열기
사용자가 "영상자료실 열어줘"(또는 "video-library 열기")를 요청하면 `vl.py open`을 실행하고 `<URL>`을 알려 준다. 영상자료실 폴더의 `영상자료실 열기.bat`(Mac은 `.command`)을 더블클릭해도 된다고 안내한다.

## 질문 답변
사용자가 영상자료실의 강의 내용에 대해 물으면(예: "그 강의에서 ○○ 설명한 부분 찾아줘", "video-library 강의 「제목」(<ID>)에 대해 질문: …"):
1. `vl.py open --no-browser`로 미니 서버를 확인(꺼져 있으면 켬)하고 출력의 `url`을 `<URL>`로 쓴다.
2. 질문의 핵심어 2~3개를 골라 **핵심어마다 따로** `vl.py search "<핵심어>"`를 실행한다(여러 단어를 한 번에 넣으면 붙여서 찾기 때문에 결과가 0건이 된다). 강의 ID가 주어졌으면 `--video <ID>`, 분야가 분명하면 `--field <분야>`를 붙인다. 결과가 없으면 비슷한 말로 한두 번 더 찾는다.
3. 찾은 장면 앞뒤 문장을 `<영상자료실>/lectures/<ID>/lecture.json`의 `segments`에서 읽어 맥락을 확인한다.
4. **영상에 근거가 있는 내용만** 한국어로 답하고, 근거 장면마다 시간과 바로 열리는 링크 `<URL>/lecture?id=<ID>&t=<초>`(검색 결과에 출력된 링크)를 붙인다. 링크는 미니 서버가 켜져 있을 때만 열린다(1시간 쓰지 않으면 꺼짐 — 영상자료실 폴더의 「영상자료실 열기」로 다시 켬). 영상에서 찾지 못했으면 그렇다고 말한다. 영상 밖 투자 조언·진단은 덧붙이지 않는다.

## 나중 요청: 업로드
사용자가 "video-library 업로드 <ID>"를 요청하면 `vl.py upload --video <ID>`를 실행하고 위 12단계처럼 결과를 안내한다. 설정이 없다는 출력이면 아래 "Railway 연결"을 안내한다.

## 나중 요청: Railway 연결(선택)
내 Railway 서버로 결과를 올리고 싶다는 요청이면:
1. Railway 서버가 이미 배포돼 있어야 한다(설치 안내서 README의 Railway 절).
2. 연결은 비밀번호를 입력받으므로 **사용자가 자기 터미널에서 직접** 실행한다. AI는 `vl.py connect`를 대신 실행하지 않는다. 비밀번호·토큰을 묻거나 출력하지 않는다. 아래 명령을 실제 경로로 바꿔 보여 주기만 한다(Railway 프로젝트에 `railway link`된 폴더에서):
   `"$PY" "$SKILL/scripts/vl.py" connect <서버 주소> --service <서비스 이름>`
3. 사용자가 끝났다고 하면 `vl.py upload --video <ID>`로 올릴 수 있다고 안내한다.

## 나중 요청: 한국어 강의 영어 번역
사용자가 "video-library 번역 <ID>"(강의 화면 [영어 번역 요청]이 복사해 주는 문장)를 요청하면:
1. `vl.py reopen --video <ID> --translate-en`
2. 위 9단계(L = `en`)
3. `vl.py assemble --video <ID>`
4. Railway 업로드 설정이 있으면(작업의 업로드 단계가 대기 중) `vl.py upload --video <ID>`로 Railway 사본도 바꾼다(위 12단계와 같은 안내).

## [맥락 브리프]
```
너는 유튜브 영상 자막 정리 파이프라인의 "맥락 파악" 단계다. 자동자막을 고치기 전에 영상 전체를 읽고 맥락표를 만든다.

입력: <W>/build/transcript.md — `[번호] [시간] 문장` 줄. 길면 나눠 읽되 끝까지 읽는다.
출력: <W>/build/context.json (UTF-8, JSON만):
{"field": "dev|finance|science|medical|other", "one_liner": "80자 이내 한국어 한 줄 소개", "topic_summary": "한국어 3~5문장 요약", "key_terms": [{"term": "올바른 표기", "heard_as": ["자막에 잘못 적힌 표기"], "note": "짧은 설명"}], "proper_nouns": ["사람·회사·제품·서비스 이름의 올바른 표기"]}

규칙:
1. field: 개발(dev), 금융·경제·투자(finance), 과학기술(science), 의학·보건(medical), 그 밖(other) 중 영상의 중심 주제 하나.
2. key_terms: 영상이 중요하게 다루는 용어와, 자동자막이 그것을 잘못 적은 형태(heard_as). heard_as에는 transcript.md에 실제로 나온 표기만 적는다(추측으로 지어내지 않는다).
3. one_liner·topic_summary는 원문 언어와 상관없이 한국어로, 영상이 말한 것에 충실하게 쓴다.
4. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind context 로 확인하고, 불합격이면 고쳐서 다시 확인한다.

끝나면 2줄로 보고: field와 key_terms 개수, 확신이 없던 점.
```

## [교정 브리프]
```
너는 유튜브 자막 정리 파이프라인의 "교정·교열" 단계다. 담당 조각 하나만 처리한다.

입력:
- <W>/build/chunks/NN.md — `[번호] [시간] 문장`. CONTEXT 블록은 읽기 전용이고, EDITABLE RANGE의 문장만 고친다.
- <W>/build/context.json — 맥락표. key_terms의 heard_as → term 이 교정 후보다.
출력: <W>/build/chunks/NN.edits.json — 바꾼 문장만 담은 JSON 배열(바꿀 것이 없으면 []):
[{"idx": 문장번호(정수), "text": "고친 문장 전체", "changes": [{"from": "원래 표기", "to": "고친 표기", "kind": "term 또는 spelling"}]}]

할 일:
1. 교정(kind "term"): 맥락표와 앞뒤 문맥으로 볼 때 명백히 잘못 인식된 용어·고유명사만 고친다(예: 기 허브→GitHub, 출론→추론).
2. 교열: 띄어쓰기·문장부호(마침표·쉼표·물음표)는 자유롭게 고친다. 이것은 changes에 적지 않는다. 맞춤법(kind "spelling", 예: 되요→돼요)은 changes에 적는다.
3. 말한 내용은 바꾸지 않는다. 군더더기(어·음·그) 지우기, 문장 다시 쓰기, 요약, 단어 추가·삭제를 하지 않는다. 숫자·단위·부호(1.5, -5, 10,000)는 그대로 둔다. 확실하지 않으면 고치지 않는다.
4. changes의 from은 원문 문장에 실제로 있는 글자 그대로, to는 바꾼 글자다. from·to는 각 20자 이내. 원래 글자를 그대로 두고 덧붙이기만 하거나 지우기만 하는 변경은 불합격이다.
5. 같은 문장에 같은 단어가 여러 번 나오는데 일부만 고칠 때는 from에 앞뒤 글자를 붙여 어느 것인지 구분한다(검사기는 처음 나오는 것부터 바꾼다).
6. 한 문장에서 바뀐 글자가 30%를 넘으면 불합격이다. 그렇게 많이 고쳐야 한다면 그 문장은 두지 않는다.
7. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind edits --chunk NN 으로 확인하고, 불합격이면 고쳐서 다시 확인한다.

끝나면 2줄로 보고: 고친 문장 수와 교정(term) 예시 몇 개, 확신이 없던 점.
```

## [목차 브리프]
```
너는 영상 전사를 2단 목차로 구조화한다.

입력: <W>/build/sentences.corrected.json — [{idx, start, end, text}] (N개, 초 단위). 길면 나눠 읽는다. <W>/build/context.json 도 참고한다.
출력: <W>/build/outline.json (JSON만):
{"chapters": [{"id": "1", "title": "...", "summary": "...", "segments": [첫 문장 번호, 끝 문장 번호], "children": [{"id": "1.1", "title": "...", "summary": "...", "segments": [a, b], "children": []}]}],
 "mentions": [{"kind": "link|book|command|other", "text": "...", "url": "https://...(링크일 때만)", "idx": 문장번호}]}

규칙:
1. 대목차 개수: 영상 10분 미만 2~4개, 60분 미만 4~10개, 그 이상 6~12개. 소목차는 0개 또는 2~6개이고, 10분 이상 영상은 대목차마다 2~6개가 필수다. 3단은 만들지 않는다(소목차의 children은 []).
2. segments는 문장 번호다(시간·단어 번호가 아님). 대목차들이 1..N을 빈틈·겹침 없이 차례로 덮고, 소목차들이 부모 범위를 정확히 덮는다. id는 "1","2",… / "1.1","1.2",… 순서.
3. 제목은 30자 이내 한국어 명사구로, 화자가 쓴 말을 위주로 한다. 대목차 요약은 3~5문장, 소목차 요약은 1~2문장. 말한 내용에 충실하게 쓰고 평가·추가는 하지 않는다. 원문 언어와 상관없이 한국어로 쓴다.
4. mentions: 화자가 언급한 사이트·책·명령어 등. 없으면 [].
5. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind outline 으로 확인하고, 불합격이면 고친다.

끝나면 2줄로 보고: 대목차·소목차 수, mentions 수와 확신이 없던 점.
```

## [용어집 브리프]
```
너는 이 영상을 보는 학습자를 위한 용어집을 만든다.

입력: <W>/build/sentences.corrected.json, <W>/build/outline.json, <W>/build/context.json
출력: <W>/build/glossary.json — [{"term": "...", "definition": "...", "analogy": "...", "claim_note": "...", "idx": 문장번호}] (JSON 배열만)

규칙:
1. 영상에서 실제로 설명하거나 다룬 용어만 넣는다(지나가며 이름만 나온 것은 제외). 20분 영상 8~25개, 3시간 영상 20~60개(길이에 비례). 처음 나온 순서로.
2. term: 표준 표기. 필요하면 한글과 영어를 함께 쓴다(예: "리포지토리(Repository)").
3. definition: 1~2문장. 그 분야에서 일반적으로 인정되는 뜻을 비전문가가 이해할 수준으로 쓴다. 영상 문장을 베끼지 않는다.
4. analogy: 핵심 원리를 담은 일상 비유 한 문장. 정직한 비유가 없으면 이 키를 뺀다.
5. claim_note: 화자가 그 용어에 대해 **사실 확인이 필요한 자기 주장·전망·권유**(예: "앞으로 금리가 내려갈 것", "○○ 종목이 가장 유망", "하루 ○번 먹으면 낫는다")를 했을 때만 정의와 섞지 말고 "영상에서는 ~라고 주장(전망·권유)한다" 형식으로 적는다. 화자가 용어의 뜻을 설명하거나 예를 든 것, 일반적으로 인정되는 사실은 claim_note가 아니다. 대부분의 용어에는 claim_note가 없다 — 용어의 3분의 1 넘게 붙었다면 다시 보고 줄인다. 없으면 이 키를 뺀다.
6. idx: 그 용어가 처음 설명된 문장 번호.
7. 모두 한국어로 쓴다. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind glossary 로 확인한다.

끝나면 2줄로 보고: 용어 수, 비유를 일부러 뺀 용어와 확신이 없던 점.
```

## [번역 브리프]
```
너는 영상 전사의 한 조각을 L 언어로 번역한다(ko = 한국어, en = 영어).

입력: <W>/build/chunks/NN.md(이 조각의 문장 번호 범위 확인용), <W>/build/sentences.corrected.json(번역할 문장 — 교정된 text), <W>/build/context.json(용어 표기)
출력: <W>/build/chunks/NN.L.json — [{"idx": 번호, "text": "번역문"}]. 이 조각의 EDITABLE RANGE 문장 전부를, 번호 순서대로, 문장 하나에 번역 하나씩.

규칙:
1. 문장을 합치거나 나누지 않는다(번호가 1:1이어야 화면에서 장면 이동이 맞는다). 문장이 중간에 끊겨 있으면 끊긴 그대로 자연스럽게 옮긴다.
2. 용어는 맥락표의 표기를 따른다. 고유명사·명령어·코드·숫자는 원문 그대로 둔다.
3. 빈 번역은 안 된다. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind translation --lang L --chunk NN 으로 확인한다.

끝나면 1줄로 보고: 번역한 문장 수와 확신이 없던 점.
```

## [FAQ 브리프]
```
너는 학습자가 이 영상에 대해 물을 법한 질문과 답을 만든다.

입력: <W>/build/sentences.corrected.json, <W>/build/outline.json
출력: <W>/build/faq.json — [{"question": "...", "answer": "...", "evidence": [근거 문장 번호, ...]}] 5~10개

규칙:
1. 답은 영상에 근거가 있는 내용만, 한국어 2~4문장으로 쓴다. evidence에 근거 문장 번호를 1개 이상 넣는다.
2. 영상 밖의 투자 조언·진단·처방을 덧붙이지 않는다. 화자의 주장은 "영상에서는 ~라고 설명합니다"처럼 전한다.
3. 핵심 개념·방법·주의점을 고루 다룬다. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind faq 로 확인한다.

끝나면 1줄로 보고: 질문 수와 확신이 없던 점.
```
