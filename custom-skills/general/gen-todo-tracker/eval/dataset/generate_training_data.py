"""Generate training dataset for gen-todo-tracker skill optimization.

TODO: Replace placeholder items with real scenarios covering all task types.
Each item must have:
  - id: unique identifier (e.g., "task-001")
  - task_type: one of the task types from adapter.get_task_types()
  - question: natural language scenario description
  - expected_commands / expected_fields / expected_points / expected: ground truth for evaluation
  - ground_truth: human-readable explanation of the correct output
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path


def generate_items() -> list[dict]:
    """Generate all training items."""
    items: list[dict] = []

    # TODO: Add items for each task type. Use "hard-" prefix for trap/difficult items
    # to ensure stratified splitting distributes them across train/val/test.
    # Easy items:
    # items.append({
    #     "id": "task-001",
    #     "task_type": "example_type",
    #     "question": "Scenario description here",
    #     "expected_commands": ["command --arg value"],
    #     "ground_truth": "Explanation of correct output",
    # })
    # Hard/trap items (id starts with "hard-"):
    # items.append({
    #     "id": "hard-001",
    #     "task_type": "example_type",
    #     "question": "Tricky scenario with semantic trap",
    #     "expected_commands": ["command --tricky-flag value"],
    #     "ground_truth": "Trap: X implies Y, not Z",
    # })

    return items


def split_and_save(
    items: list[dict],
    output_dir: str | Path,
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
    seed: int = 42,
) -> None:
    """Stratified split: ensure hard and easy items are distributed across all splits."""
    output_dir = Path(output_dir)
    rng = random.Random(seed)

    hard_items = [it for it in items if it["id"].startswith("hard-")]
    easy_items = [it for it in items if not it["id"].startswith("hard-")]

    rng.shuffle(hard_items)
    rng.shuffle(easy_items)

    def _split_list(lst, ratios):
        n = len(lst)
        n_train = int(n * ratios[0])
        n_val = int(n * ratios[1])
        return lst[:n_train], lst[n_train:n_train + n_val], lst[n_train + n_val:]

    hard_splits = _split_list(hard_items, ratios)
    easy_splits = _split_list(easy_items, ratios)

    splits = {
        "train": hard_splits[0] + easy_splits[0],
        "val": hard_splits[1] + easy_splits[1],
        "test": hard_splits[2] + easy_splits[2],
    }

    for split_name, split_items in splits.items():
        split_dir = output_dir / split_name
        split_dir.mkdir(parents=True, exist_ok=True)
        with open(split_dir / "items.json", "w", encoding="utf-8") as f:
            json.dump(split_items, f, ensure_ascii=False, indent=2)
        print(f"  {split_name}: {len(split_items)} items")

    n = len(items)
    manifest = {
        "name": "GenTodoTracker",
        "total": n,
        "splits": {k: len(v) for k, v in splits.items()},
        "ratios": list(ratios),
        "seed": seed,
    }
    with open(output_dir / "split_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    items = generate_items()
    print(f"Generated {len(items)} items")
    script_dir = Path(__file__).resolve().parent
    split_and_save(items, script_dir)
