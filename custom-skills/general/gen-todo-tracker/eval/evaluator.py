"""{skill_name} evaluator — strict CLI command matching.

Scoring dimensions (5 points total, em requires >= 4.5):
1. Script path (1pt) — correct script/command present
2. URL exact match (1pt) — URL value matches expected (normalized)
3. Required flags present (1pt) — all expected flags appear
4. No extra flags (0.5pt) — no unexpected flags beyond safe defaults
5. Parameter values exact (1.5pt) — numeric/choice params match expected values
"""
from __future__ import annotations

import re


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    m = re.match(r"^([A-Za-z]+://)?([^/]+)(.*)", url)
    if m:
        scheme = (m.group(1) or "").lower()
        host = m.group(2).lower()
        path = m.group(3)
        return f"{scheme}{host}{path}"
    return url.lower()


def _extract_url(cmd: str) -> str:
    # Try --url '...' first, then positional URL
    m = re.search(r"--url\s+['\"]?([^'\"\s]+)['\"]?", cmd)
    if m:
        return m.group(1)
    m = re.search(r"(https?://[^\s'\"]+)", cmd)
    return m.group(1) if m else ""


def _extract_flags(cmd: str) -> set[str]:
    flags = set()
    for m in re.finditer(r"--([a-zA-Z][\w-]*)", cmd):
        flags.add(m.group(1))
    return flags


def _extract_flag_value(cmd: str, flag: str) -> str:
    m = re.search(rf"--{flag}\s+['\"]?([^'\"\s]+)['\"]?", cmd)
    return m.group(1) if m else ""


# Flags that carry a value (not boolean)
_VALUE_FLAGS = {
    "timeout", "wait-ms", "login-wait-s", "manual-wait-s",
    "storage-state", "save-storage", "wait-until", "format",
    "iframe-selector", "cookie", "cookie-file",
}

# Flags safe to include even if not expected
_SAFE_EXTRA_FLAGS = {"url"}


def evaluate_output(
    predicted: str,
    expected_commands: list[str],
) -> dict:
    """Strictly evaluate predicted command for {skill_name}."""
    if not expected_commands:
        return {"em": 1.0, "f1": 1.0, "predicted_commands": predicted.strip(), "match_count": 0, "expected_count": 0}

    predicted_lines = [
        line.strip() for line in predicted.split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    predicted_cmd = predicted_lines[0] if predicted_lines else ""
    expected_cmd = expected_commands[0] if expected_commands else ""

    score = 0.0
    max_score = 5.0
    details = {}

    # 1. Script path (1pt) — check if expected script/command appears in predicted
    # Extract the script/command part (first meaningful token after python3)
    exp_script = expected_cmd.split()
    script_match = False
    for part in exp_script:
        if part.endswith(".py") or part in ("dws", "kb", "git"):
            if part in predicted_cmd:
                script_match = True
                break
    if not script_match:
        # Fallback: check if predicted contains any .py from expected
        for part in expected_cmd.split():
            if ".py" in part and part in predicted_cmd:
                script_match = True
                break
    if script_match:
        score += 1.0
    details["script_path"] = script_match

    # 2. URL exact match (1pt)
    pred_url = _extract_url(predicted_cmd)
    exp_url = _extract_url(expected_cmd)
    url_match = bool(pred_url) and _normalize_url(pred_url) == _normalize_url(exp_url)
    if url_match:
        score += 1.0
    details["url_match"] = url_match

    # 3. Required flags present (1pt)
    pred_flags = _extract_flags(predicted_cmd)
    exp_flags = _extract_flags(expected_cmd)
    exp_flags.discard("url")
    pred_flags.discard("url")
    missing_flags = exp_flags - pred_flags
    if not missing_flags:
        score += 1.0
    details["flags_present"] = not missing_flags
    details["missing_flags"] = sorted(missing_flags)

    # 4. No extra flags (0.5pt)
    extra_flags = pred_flags - exp_flags - _SAFE_EXTRA_FLAGS
    if not extra_flags:
        score += 0.5
    details["no_extra_flags"] = not extra_flags
    details["extra_flags"] = sorted(extra_flags)

    # 5. Parameter values exact (1.5pt)
    value_score = 0.0
    checked_values = 0
    for flag in exp_flags:
        if flag not in _VALUE_FLAGS:
            continue
        exp_val = _extract_flag_value(expected_cmd, flag)
        if not exp_val:
            continue
        pred_val = _extract_flag_value(predicted_cmd, flag)
        checked_values += 1
        if pred_val == exp_val:
            value_score += 1.0
        elif flag == "wait-until":
            valid_choices = {"commit", "domcontentloaded", "load", "networkidle"}
            if pred_val.lower() in valid_choices:
                value_score += 0.3
        elif flag == "format":
            pass  # format mismatch = 0
        elif flag in {"timeout", "wait-ms", "login-wait-s", "manual-wait-s"}:
            try:
                ratio = float(pred_val) / float(exp_val)
                if 0.9 <= ratio <= 1.1:
                    value_score += 0.5
            except (ValueError, ZeroDivisionError):
                pass

    if checked_values > 0:
        per_flag = 1.5 / checked_values
        score += value_score * per_flag
    else:
        score += 1.5
    details["value_check"] = {"checked": checked_values, "correct": int(value_score)}

    em = 1.0 if score >= 4.5 else 0.0
    f1 = score / max_score

    return {
        "em": em,
        "f1": f1,
        "predicted_commands": predicted_cmd,
        "match_count": round(score, 2),
        "expected_count": max_score,
        "details": details,
    }
