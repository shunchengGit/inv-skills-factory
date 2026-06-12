"""gen-todo-tracker task dataloader."""
from __future__ import annotations

import json

from skillopt.datasets.base import SplitDataLoader


class GenTodoTrackerDataLoader(SplitDataLoader):
    """GenTodoTracker dataloader.

    Each split directory (train/, val/, test/) contains items.json —
    a JSON array of task items.
    """

    def load_raw_items(self, data_path: str) -> list[dict]:
        with open(data_path) as f:
            content = f.read().strip()
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data") or list(data.values())
        return []
