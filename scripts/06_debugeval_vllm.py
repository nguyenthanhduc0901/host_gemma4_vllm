from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---- Defaults (edit these in-file if you want) ----
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_VENV_PY = os.path.join(_REPO_DIR, ".venv", "bin", "python")

DATA_PATH = os.path.join(_REPO_DIR, "data", "debugeval", "debugevalsuite_task124.jsonl")
TASKS = [1, 2, 4]
LIMIT_PER_TASK = 10
SEED = 123

VLLM_BASE_URL = "http://127.0.0.1:8000"
VLLM_SERVED_MODEL = "gemma-4-e4b-it"
VLLM_TIMEOUT_S = 120.0

GEMINI_MODEL = "gemini-2.5-flash"

TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 32

DOTENV_PATH = os.path.join(_REPO_DIR, ".env")
OUT_JSON = os.path.join(_REPO_DIR, "outputs", "debugeval_compare_test.json")


_CHOICE_RE = re.compile(r"\(([ABCD])\)")
_BOOL_RE = re.compile(r"\b(true|false)\b", re.IGNORECASE)


@dataclass
class Example:
    question_id: str
    task: int
    prompt: str
    gold: str
    source: Dict[str, Any]


def _load_dotenv_if_present(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        return


def _read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _normalize_choice(text: str) -> str:
    if not text:
        return ""
    m = _CHOICE_RE.search(text)
    return f"({m.group(1)})" if m else ""


def _normalize_bool(text: str) -> str:
    if not text:
        return ""
    m = _BOOL_RE.search(text)
    if not m:
        return ""
    return "True" if m.group(1).lower() == "true" else "False"


def _example_key(ex: Example) -> str:
    return f"{ex.question_id}#task{ex.task}"


def _make_task1_prompt(rec: Dict[str, Any]) -> Optional[Example]:
    opts = str(rec.get("task1_options", "") or "").strip()
    ans = str(rec.get("task1_answer", "") or "").strip()
    t = str(rec.get("task1_type", "") or "").strip()
    if not (opts and ans and t):
        return None

    question_title = rec.get("question_title", "")
    question_content = rec.get("question_content", "")
    buggy_code = rec.get("buggy_code", "")

    prompt = (
        "You are given a programming problem and a buggy solution. "
        "Task 1 (Bug localization): choose which option contains the buggy snippet.\n\n"
        "Rules:\n"
        "- Answer with exactly one of: (A), (B), (C), (D).\n"
        "- Do not add any other text.\n\n"
        f"Problem title: {question_title}\n\n"
        f"Problem:\n{question_content}\n\n"
        f"Buggy code:\n{buggy_code}\n\n"
        "Options:\n"
        f"{opts}\n"
        "Answer:"
    )

    source = {
        "question_id": str(rec.get("question_id", "")),
        "question_title": rec.get("question_title", ""),
        "question_content": rec.get("question_content", ""),
        "platform": rec.get("platform", ""),
        "language": rec.get("language", ""),
        "difficulty": rec.get("difficulty", ""),
        "buggy_code": rec.get("buggy_code", ""),
        "task1_options": rec.get("task1_options", ""),
        "task1_type": rec.get("task1_type", ""),
    }

    return Example(question_id=str(rec.get("question_id", "")), task=1, prompt=prompt, gold=ans, source=source)


def _make_task2_prompt(rec: Dict[str, Any]) -> Optional[Example]:
    gold = str(rec.get("task2_choice", "") or "").strip()
    if not gold:
        return None

    question_title = rec.get("question_title", "")
    question_content = rec.get("question_content", "")
    buggy_code = rec.get("buggy_code", "")

    prompt = (
        "Task 2 (Major error type classification).\n\n"
        "Choose the best major error type for the buggy code.\n\n"
        "Options:\n"
        "(A) syntax error\n"
        "(B) reference error\n"
        "(C) logic error\n"
        "(D) multiple error\n\n"
        "Rules:\n"
        "- Answer with exactly one of: (A), (B), (C), (D).\n"
        "- Do not add any other text.\n\n"
        f"Problem title: {question_title}\n\n"
        f"Problem:\n{question_content}\n\n"
        f"Buggy code:\n{buggy_code}\n\n"
        "Answer:"
    )

    source = {
        "question_id": str(rec.get("question_id", "")),
        "question_title": rec.get("question_title", ""),
        "question_content": rec.get("question_content", ""),
        "platform": rec.get("platform", ""),
        "language": rec.get("language", ""),
        "difficulty": rec.get("difficulty", ""),
        "buggy_code": rec.get("buggy_code", ""),
        "major_error_type": rec.get("major_error_type", ""),
        "minor_error_type": rec.get("minor_error_type", ""),
    }

    return Example(question_id=str(rec.get("question_id", "")), task=2, prompt=prompt, gold=gold, source=source)


def _make_task4_prompt(rec: Dict[str, Any]) -> Optional[Example]:
    gold = str(rec.get("task4", "") or "").strip()
    if gold not in {"True", "False"}:
        return None

    question_title = rec.get("question_title", "")
    question_content = rec.get("question_content", "")
    buggy_code = rec.get("buggy_code", "")

    prompt = (
        "Task 4 (Pass/fail prediction).\n\n"
        "Given the problem and the submitted solution code, predict whether the submission would FAIL at least one test case "
        "(including compile errors, runtime errors, wrong answers, or timeouts).\n\n"
        "Rules:\n"
        "- Answer with exactly one token: True or False.\n"
        "- Do not add any other text.\n\n"
        f"Problem title: {question_title}\n\n"
        f"Problem:\n{question_content}\n\n"
        f"Submitted code:\n{buggy_code}\n\n"
        "Answer (True=fail, False=pass):"
    )

    source = {
        "question_id": str(rec.get("question_id", "")),
        "question_title": rec.get("question_title", ""),
        "question_content": rec.get("question_content", ""),
        "platform": rec.get("platform", ""),
        "language": rec.get("language", ""),
        "difficulty": rec.get("difficulty", ""),
        "buggy_code": rec.get("buggy_code", ""),
        "major_error_type": rec.get("major_error_type", ""),
        "minor_error_type": rec.get("minor_error_type", ""),
    }

    return Example(question_id=str(rec.get("question_id", "")), task=4, prompt=prompt, gold=gold, source=source)


def _collect_examples(path: str) -> List[Example]:
    makers = {1: _make_task1_prompt, 2: _make_task2_prompt, 4: _make_task4_prompt}
    per_task: Dict[int, List[Example]] = {t: [] for t in TASKS}
    for rec in _read_jsonl(path):
        for t in TASKS:
            ex = makers[t](rec)
            if ex is not None:
                per_task[t].append(ex)

    rng = random.Random(SEED)
    chosen: List[Example] = []
    for t in TASKS:
        rng.shuffle(per_task[t])
        chosen.extend(per_task[t][:LIMIT_PER_TASK])
    rng.shuffle(chosen)
    return chosen


def _http_post_json(url: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code} from {url}: {body[:2000]}") from e
    except Exception as e:
        raise RuntimeError(f"Request failed to {url}: {e}") from e

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Non-JSON response from {url}: {raw[:2000]}") from e


def _extract_text_from_openai_compat(resp: Dict[str, Any]) -> str:
    if isinstance(resp, dict) and isinstance(resp.get("output"), list):
        parts: List[str] = []
        for item in resp.get("output", []):
            for c in item.get("content", []) or []:
                if c.get("type") == "output_text":
                    parts.append(c.get("text", ""))
        return "".join(parts).strip() if parts else ""

    if isinstance(resp, dict) and isinstance(resp.get("choices"), list):
        parts: List[str] = []
        for ch in resp.get("choices", []):
            msg = ch.get("message") or {}
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                parts.append(msg["content"])
        return "\n".join(parts).strip() if parts else ""

    text = resp.get("text") if isinstance(resp, dict) else None
    return text.strip() if isinstance(text, str) else ""


def _predict_vllm(prompt: str) -> Tuple[str, float]:
    url = VLLM_BASE_URL.rstrip("/") + "/v1/responses"
    payload = {
        "model": VLLM_SERVED_MODEL,
        "input": prompt,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    t0 = time.time()
    resp = _http_post_json(url, payload, timeout_s=VLLM_TIMEOUT_S)
    return _extract_text_from_openai_compat(resp), time.time() - t0


def _make_gemini_client():
    try:
        from google import genai
    except Exception as e:
        # If the repo has a venv, try to transparently re-run with it.
        if os.path.exists(_VENV_PY) and os.environ.get("_DEBUEVAL_REEXEC") != "1" and os.path.abspath(sys.executable) != os.path.abspath(_VENV_PY):
            os.environ["_DEBUEVAL_REEXEC"] = "1"
            os.execv(_VENV_PY, [_VENV_PY, os.path.abspath(__file__), *sys.argv[1:]])

        hint = f"\nHint: run with: {_VENV_PY} {os.path.abspath(__file__)} --mode test" if os.path.exists(_VENV_PY) else ""
        raise RuntimeError("google-genai is not installed for this Python. Install: python -m pip install -U google-genai" + hint) from e

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY (put it in .env or export it).")
    return genai.Client(api_key=api_key)


def _predict_gemini(client: Any, prompt: str) -> Tuple[str, float]:
    from google.genai import types

    cfg = types.GenerateContentConfig(temperature=TEMPERATURE, max_output_tokens=MAX_OUTPUT_TOKENS)
    t0 = time.time()
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=cfg)
    dt = time.time() - t0

    text = getattr(resp, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip(), dt
    return str(resp), dt


def _print_compare_table(rows: List[Dict[str, Any]]) -> None:
    headers = ["i", "key", "gold", "gemma", "gemini"]
    widths = {"i": 4, "key": 26, "gold": 8, "gemma": 8, "gemini": 8}
    print(" ".join(h.ljust(widths[h]) for h in headers))
    print(" ".join("-" * widths[h] for h in headers))
    for r in rows:
        print(
            str(r["i"]).ljust(widths["i"])
            + " "
            + str(r["key"])[: widths["key"]].ljust(widths["key"])
            + " "
            + str(r["gold"])[: widths["gold"]].ljust(widths["gold"])
            + " "
            + str(r["gemma_pred"])[: widths["gemma"]].ljust(widths["gemma"])
            + " "
            + str(r["gemini_pred"])[: widths["gemini"]].ljust(widths["gemini"])
        )


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--mode", default="test", choices=["test"], help="test: 10 samples/task + table + 1 JSON")
    _ = ap.parse_args()

    _load_dotenv_if_present(DOTENV_PATH)

    if not os.path.exists(DATA_PATH):
        print(f"Missing dataset file: {DATA_PATH}", file=sys.stderr)
        return 2

    examples = _collect_examples(DATA_PATH)
    if not examples:
        print("No examples found in dataset.", file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(OUT_JSON) or ".", exist_ok=True)

    client = _make_gemini_client()

    rows: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {}
    correct_gemma = {t: 0 for t in TASKS}
    correct_gemini = {t: 0 for t in TASKS}
    total = {t: 0 for t in TASKS}

    for i, ex in enumerate(examples, start=1):
        gemma_raw, gemma_dt = "", 0.0
        gemini_raw, gemini_dt = "", 0.0

        try:
            gemma_raw, gemma_dt = _predict_vllm(ex.prompt)
        except Exception as e:
            gemma_raw = f"__ERROR__: {e}"

        try:
            gemini_raw, gemini_dt = _predict_gemini(client, ex.prompt)
        except Exception as e:
            gemini_raw = f"__ERROR__: {e}"

        gemma_err = gemma_raw.startswith("__ERROR__")
        gemini_err = gemini_raw.startswith("__ERROR__")

        if ex.task in (1, 2):
            gemma_pred = "ERR" if gemma_err else _normalize_choice(gemma_raw)
            gemini_pred = "ERR" if gemini_err else _normalize_choice(gemini_raw)
        else:
            gemma_pred = "ERR" if gemma_err else _normalize_bool(gemma_raw)
            gemini_pred = "ERR" if gemini_err else _normalize_bool(gemini_raw)

        ok_gemma = gemma_pred == ex.gold
        ok_gemini = gemini_pred == ex.gold

        key = _example_key(ex)
        total[ex.task] += 1
        correct_gemma[ex.task] += int(ok_gemma)
        correct_gemini[ex.task] += int(ok_gemini)

        row = {
            "i": i,
            "key": key,
            "task": ex.task,
            "gold": ex.gold,
            "gemma_pred": gemma_pred,
            "gemini_pred": gemini_pred,
        }
        rows.append(row)

        report[key] = {
            "task": ex.task,
            "gold": ex.gold,
            "question": ex.source,
            "pred_gemma": gemma_pred,
            "pred_gemini": gemini_pred,
            "ok_gemma": ok_gemma,
            "ok_gemini": ok_gemini,
            "raw_response_gemma": gemma_raw,
            "raw_response_gemini": gemini_raw,
            "latency_s_gemma": round(gemma_dt, 3),
            "latency_s_gemini": round(gemini_dt, 3),
            "vllm_base_url": VLLM_BASE_URL,
            "vllm_served_model": VLLM_SERVED_MODEL,
            "gemini_model": GEMINI_MODEL,
        }

    print("\n== Summary ==")
    for t in TASKS:
        n = total[t] or 0
        a = (correct_gemma[t] / n) if n else 0.0
        b = (correct_gemini[t] / n) if n else 0.0
        print(f"Task {t}: gemma {correct_gemma[t]}/{n}={a:.3f} | gemini {correct_gemini[t]}/{n}={b:.3f}")

    for t in TASKS:
        task_rows = [r for r in rows if r["task"] == t]
        print(f"\n== Compare: Task {t} (n={len(task_rows)}) ==")
        _print_compare_table(task_rows)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nWrote JSON: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
