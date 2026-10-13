"""Reports on disk: one file per report, one for its samples, one pointer.

Publishing is moving the pointer. A report exists as soon as an evaluation
finishes, but the page shows only the one that was published, so a half-good
run does not become the public number by being the most recent file.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
DEFAULT_ROOT = Path("reports") / "guide"


class ReportStore:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or os.environ.get("GUIDE_REPORTS_DIR") or DEFAULT_ROOT)

    def _path(self, report_id: str, suffix: str) -> Path | None:
        # The id arrives from a URL. Anything that is not a plain token is
        # simply not a report, which also keeps it inside this directory.
        return self.root / f"{report_id}{suffix}" if SAFE_ID.fullmatch(report_id) else None

    def _read(self, path: Path | None):
        return json.loads(path.read_text("utf-8")) if path is not None and path.is_file() else None

    def put(self, report: dict, samples: dict[str, dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for suffix, data in ((".json", report), (".samples.json", samples)):
            path = self._path(report["report_id"], suffix)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False) + "\n", "utf-8"
            )

    def get(self, report_id: str) -> dict | None:
        return self._read(self._path(report_id, ".json"))

    def sample(self, report_id: str, question_id: str) -> dict | None:
        samples = self._read(self._path(report_id, ".samples.json"))
        return samples.get(question_id) if samples else None

    def publish(self, report_id: str) -> bool:
        if self.get(report_id) is None:
            return False
        (self.root / "latest.json").write_text(json.dumps({"report_id": report_id}) + "\n", "utf-8")
        return True

    def latest(self) -> dict | None:
        pointer = self._read(self.root / "latest.json")
        return self.get(pointer["report_id"]) if pointer else None
