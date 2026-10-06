# 2026-10-05 1단계(약속) 구현 기록

브랜치 `feat/stage1-contract`, 계획 [2026-10-05-stage1-contract.md](../plans/2026-10-05-stage1-contract.md), 실행 방식: 직접 실행(Claude Code).

## 한 일
- Task 1: 표준 라이브러리만 쓰는 JSON Schema 부분집합 검사기(`schemacheck.py`), pytest 설정
- Task 2: `lecture.schema.json`, 직접 쓴 8분짜리 샘플 강의, 강의 정보·문장 검사
- Task 3: 2단 목차 검사(개수·빈틈·겹침·id 순서·시간 일치)
- Task 4: 번역 1:1, 참조 번호, 건너뛴 단계(glossary·translate·faq) 검사
- Task 5: 교정·교열 검사 — 띄어쓰기·문장부호 외 변경은 선언해야 하고, 삭제·30% 초과 변경은 불합격
- Task 6: AI 중간 결과(맥락표·목차) 검사
- Task 7: `vl.py validate` 명령(BOM 파일, Windows cp949 콘솔 대응)
- Task 8: API 문서 [`docs/api.md`](../../api.md)

각 Task는 테스트를 먼저 쓰고 실패(모듈·함수 없음)를 확인한 뒤 구현했다.

## 실행한 검증
- `python -m pytest` → `83 passed` (Task 8 시점) → 검토 수정 후 `python -m pytest -W error` → `90 passed`
- `python plugin/video-library/skills/video-library/scripts/vl.py validate plugin/video-library/skills/video-library/tests/fixtures/sample_lecture.json` → `통과`

## 결과
- 성공: 90개 테스트 통과(경고를 오류로 취급해도 통과), 샘플 검사 통과.
- 실패: 없음.
- 미확인: Python 3.10에서의 실행(이 PC는 3.14만 있음).

## 최종 검토 (독립 검토 에이전트, 3694e9c..8859375)
- 결과: 치명 0, 중요 5, 사소 8. 검토 집중 항목 5개(참/거짓 값, 문자열 번호, 빈 문장, BOM, cp949)는 모두 통과 확인.
- 중요 5건 수정(커밋 `89365aa`, 각각 실패 테스트를 먼저 쓰고 통과시킴):
  1. 교열 비교에서 숫자의 소수점·부호가 사라져 `1.5mg → 15mg`, `-5 → 5` 변경이 통과하던 문제
  2. 끼워 넣은 글자가 30% 비율 계산에 빠지던 문제
  3. 형식 검사의 `$`가 끝의 줄바꿈을 허용하던 문제(`"영상ID
"` 통과)
  4. `NaN`·`Infinity` 값이 통과하던 문제(브라우저가 못 읽는 파일)
  5. `check_chapters`를 직접 부를 때 잘못된 입력에 예외가 나던 문제
- 내린 판단: 비율은 "지운 쪽·더한 쪽 중 긴 쪽"으로 센다. 그래서 짧은 문장의 한→영 용어 교정은 더 자주 30%에 걸릴 수 있다. 한 글자 부정어 삽입("안")은 비율로 못 막고 `corrections` 기록으로만 드러난다.
- 미룬 사소한 사항(2단계 이후 필요할 때 처리):
  - 띄어쓰기만 바꾼 `changes` 선언이 통과해 가짜 교정 기록이 됨
  - 30% 문구가 반올림으로 "30%로 30% 초과"가 될 수 있음
  - 짧은 문장의 정당한 용어 교정이 30%에 걸림, 같은 단어의 두 번째 교정은 `from`에 앞뒤 글자를 넣어야 함 → 2단계 교정 브리프에 안내
  - `vl.py validate`가 cp949로 저장된 파일·폴더 경로에서 파이썬 오류 화면을 보임
  - 공백뿐인 문장·목차 제목·요약이 통과
  - `processed_at` 끝의 `Z`가 Python 3.10에서만 거부됨
  - 오류 문구의 `—`가 `vl.py`를 거치지 않고 cp949 콘솔에 출력되면 깨질 수 있음
  - `check_edits`의 `originals` 키가 문자열이면 모든 교정이 실패 → 2단계에서 정수 키로 넘길 것
