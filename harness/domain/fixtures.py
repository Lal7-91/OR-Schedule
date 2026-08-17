from __future__ import annotations

from pathlib import Path

import yaml

from harness.domain.models import ProblemInstance


def load_toy_problem(path: str | Path) -> ProblemInstance:
    data = yaml.safe_load(Path(path).read_text())
    return ProblemInstance.model_validate(data)
