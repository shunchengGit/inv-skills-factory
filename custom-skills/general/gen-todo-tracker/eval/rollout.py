"""gen-todo-tracker rollout — single-turn generation + batch execution."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from skillopt.model import chat_target
from .evaluator import evaluate_output as evaluate_commands


# ── Prompt builders ────────────────────────────────────────────────────────

def _build_system(skill_content: str, system_prompt_template: str) -> str:
    if skill_content.strip():
        skill_section = f"## Skill\n{skill_content.strip()}\n\n"
    else:
        skill_section = ""
    return system_prompt_template.format(skill_section=skill_section)


def _build_user(question: str, task_type: str = "") -> str:
    parts = [f"## Scenario\n{question}"]
    if task_type:
        parts.append(f"## Task Type\n{task_type}")
    parts.append(
        "## Instructions\n"
        "Produce the correct output based on the skill instructions above.\n"
        "Do NOT include explanation — only the requested output."
    )
    return "\n\n".join(parts)


# ── Single-item execution ──────────────────────────────────────────────────

def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    system_prompt_template: str,
    max_completion_tokens: int = 16384,
    exec_timeout: int = 120,
) -> dict:
    """Process a single item: run agent + evaluate."""
    item_id = str(item["id"])
    question = item.get("question", "")
    task_type = item.get("task_type", "")
    expected_commands = item.get("expected_commands", [])
    ground_truth = item.get("ground_truth", "")

    result = {
        "id": item_id,
        "question": question,
        "task_type": task_type,
        "hard": 0,
        "soft": 0.0,
        "predicted_answer": "",
        "fail_reason": "",
        "agent_ok": False,
        "n_turns": 0,
    }

    try:
        pred_dir = os.path.join(out_root, "predictions", item_id)
        os.makedirs(pred_dir, exist_ok=True)

        system = _build_system(skill_content, system_prompt_template)
        user = _build_user(question, task_type)

        response, _ = chat_target(
            system=system,
            user=user,
            max_completion_tokens=max_completion_tokens,
            retries=3,
            stage="rollout",
            timeout=exec_timeout,
        )

        result["response"] = response
        result["agent_ok"] = True
        result["n_turns"] = 1

        with open(os.path.join(pred_dir, "target_system_prompt.txt"), "w") as f:
            f.write(system)
        with open(os.path.join(pred_dir, "target_user_prompt.txt"), "w") as f:
            f.write(user)

        eval_result = evaluate_commands(response, expected_commands)
        result["em"] = eval_result["em"]
        result["f1"] = eval_result["f1"]
        result["hard"] = int(eval_result["em"])
        result["soft"] = eval_result["f1"]
        result["predicted_answer"] = response.strip()

        if eval_result["em"] < 1.0:
            result["fail_reason"] = f"F1={eval_result['f1']:.2f}: matched {eval_result['match_count']}/{eval_result['expected_count']}"

        conversation = [
            {"type": "message", "turn": 1, "content": response},
        ]
        eval_detail = (
            f"[EVALUATION RESULT]\n"
            f"Scenario: {question[:200]}\n"
            f"Ground truth: {ground_truth}\n"
            f"Match: {eval_result['match_count']}/{eval_result['expected_count']}\n"
            f"EM: {eval_result['em']}\n"
            f"F1: {eval_result['f1']:.4f}"
        )
        conversation.append({"role": "system", "content": eval_detail})
        with open(os.path.join(pred_dir, "conversation.json"), "w") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)

    except Exception as e:
        result["fail_reason"] = f"error: {e}"

    return result


# ── Batch execution ────────────────────────────────────────────────────────

def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    system_prompt_template: str,
    max_completion_tokens: int = 16384,
    exec_timeout: int = 120,
    workers: int = 8,
    task_timeout: int = 600,
    **kwargs,
) -> list[dict]:
    """Run agent on all items with ThreadPoolExecutor. Resume-aware."""
    results_path = os.path.join(out_root, "results.jsonl")
    os.makedirs(out_root, exist_ok=True)

    done_ids: set[str] = set()
    existing: list[dict] = []
    if os.path.exists(results_path):
        with open(results_path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done_ids.add(str(r["id"]))
                    existing.append(r)
                except Exception:
                    pass

    pending = [it for it in items if str(it["id"]) not in done_ids]
    if not pending:
        return existing

    total = len(existing) + len(pending)
    completed = len(existing)
    correct_count = sum(1 for r in existing if r.get("hard", 0))
    if existing:
        print(f"    [rollout] resuming: {completed}/{total} already done", flush=True)

    results = list(existing)

    def _timeout_result(item: dict) -> dict:
        return {
            "id": str(item["id"]),
            "question": item.get("question", ""),
            "task_type": item.get("task_type") or "gen-todo-tracker",
            "hard": 0, "soft": 0.0, "predicted_answer": "",
            "response": "", "fail_reason": f"task-timeout-{task_timeout}s",
            "agent_ok": False, "n_turns": 0,
        }

    started_at: dict[str, float] = {}

    def _run_one(item: dict) -> dict:
        started_at[str(item["id"])] = time.time()
        return process_one(item, out_root, skill_content, system_prompt_template, max_completion_tokens, exec_timeout)

    with open(results_path, "a") as outf:
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futs = {ex.submit(_run_one, it): it for it in pending}
            pending_futs = set(futs)
            while pending_futs:
                done, _ = wait(pending_futs, timeout=5, return_when=FIRST_COMPLETED)
                now = time.time()
                timed_out = [
                    fut for fut in pending_futs - done
                    if str(futs[fut]["id"]) in started_at
                    and now - started_at[str(futs[fut]["id"])] >= task_timeout
                ]
                for fut in done:
                    pending_futs.remove(fut)
                    item = futs[fut]
                    try:
                        res = fut.result()
                    except Exception as exc:
                        res = _timeout_result(item)
                        res["fail_reason"] = f"unexpected: {type(exc).__name__}: {exc}"
                    results.append(res)
                    completed += 1
                    if res.get("hard", 0):
                        correct_count += 1
                    acc = correct_count / completed if completed else 0
                    print(f"    [rollout] {completed}/{total} (acc={acc:.3f}) id={res['id']} hard={res.get('hard', '?')}", flush=True)
                    outf.write(json.dumps(res, ensure_ascii=False) + "\n")
                    outf.flush()
                for fut in timed_out:
                    pending_futs.remove(fut)
                    fut.cancel()
                    res = _timeout_result(futs[fut])
                    results.append(res)
                    completed += 1
                    acc = correct_count / completed if completed else 0
                    print(f"    [rollout] {completed}/{total} (acc={acc:.3f}) id={res['id']} TIMEOUT", flush=True)
                    outf.write(json.dumps(res, ensure_ascii=False) + "\n")
                    outf.flush()
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    return results
