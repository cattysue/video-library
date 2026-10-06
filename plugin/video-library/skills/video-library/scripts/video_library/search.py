"""전체 강의 통합 검색(메모리 색인). 미니 서버와 vl.py search 가 같이 쓴다."""
from __future__ import annotations

import argparse
import json
import unicodedata

from .config import fmt_time, library_home, server_url, video_id_arg
from .store_file import FileStore

FIELDS = ("dev", "finance", "science", "medical", "other")
MAX_HITS_PER_LECTURE = 20
_WHERE_LABELS = {"title": "제목", "chapter": "목차", "glossary": "용어집", "segment": "전사", "translation": "번역"}


def normalize_query(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFC", text).casefold() if not ch.isspace())


def _walk(chapters: list):
    for ch in chapters:
        yield ch
        yield from _walk(ch.get("children") or [])


class SearchIndex:
    def __init__(self, lectures: list[dict]):
        self._docs = []
        for doc in lectures:
            lec = doc["lecture"]
            starts = {s["idx"]: s["start"] for s in doc["segments"]}
            rows = [("title", None, 0.0, lec["title"], None)]
            for ch in _walk(doc["chapters"]):
                rows.append(("chapter", ch["segments"][0], ch["start"], f"{ch['title']} — {ch['summary']}", None))
            for g in doc["glossary"]:
                rows.append(("glossary", g["idx"], starts.get(g["idx"], 0.0), f"{g['term']}: {g['definition']}", None))
            for s in doc["segments"]:
                rows.append(("segment", s["idx"], s["start"], s["text"], lec["language"]))
            for lang, items in doc["translations"].items():
                for it in items:
                    rows.append(("translation", it["idx"], starts.get(it["idx"], 0.0), it["text"], lang))
            self._docs.append((lec, [(w, i, t, text, lang, normalize_query(text)) for w, i, t, text, lang in rows]))

    def search(self, query: str, field: str | None = None, video: str | None = None,
               limit: int = MAX_HITS_PER_LECTURE, allowed: set[str] | None = None) -> dict:
        needle = normalize_query(query or "")
        results = []
        if needle:
            for lec, rows in self._docs:
                if (field and lec["field"] != field) or (video and lec["id"] != video):
                    continue
                if allowed is not None and lec["id"] not in allowed:
                    continue
                hits = []
                for where, idx, start, text, lang, normed in rows:
                    if needle in normed:
                        hit = {"where": where, "idx": idx, "start": start, "text": text}
                        if lang:
                            hit["lang"] = lang
                        hits.append(hit)
                        if len(hits) >= limit:
                            break
                if hits:
                    results.append({"id": lec["id"], "title": lec["title"], "field": lec["field"], "hits": hits})
        return {"query": query, "results": results}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py search", description="영상자료실의 모든 강의에서 검색한다(대화창 질문 답변용).")
    ap.add_argument("query", help="검색어")
    ap.add_argument("--field", choices=FIELDS, default=None)
    ap.add_argument("--video", type=video_id_arg, default=None, help="이 강의 안에서만")
    ap.add_argument("--limit", type=int, default=MAX_HITS_PER_LECTURE)
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    a = ap.parse_args(argv)
    home = library_home()
    result = SearchIndex(FileStore(home).all_lectures()).search(a.query, a.field, a.video, a.limit)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not result["results"]:
        print("검색 결과가 없습니다.")
        return 0
    base = server_url(home)
    for r in result["results"]:
        print(f"■ {r['title']} ({r['id']})")
        for h in r["hits"]:
            label = _WHERE_LABELS[h["where"]] + (f" {h['lang'].upper()}" if h.get("lang") else "")
            print(f"  [{fmt_time(h['start'])}] ({label}) {h['text'][:160]}")
            print(f"    {base}/lecture?id={r['id']}&t={int(h['start'])}")
    return 0
