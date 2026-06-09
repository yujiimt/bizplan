"""ローカル実行台帳（resume の真実）。

Notion は人が読む成果物 SoT、こちらは実行・再開のための台帳。二層構成。
artifact の本文は runs/<run_id>/<agent_id>.md に、structured は .json に保存する。
"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Any

from . import config


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Ledger:
    def __init__(self) -> None:
        config.ROOT.mkdir(parents=True, exist_ok=True)
        config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self.path = config.LEDGER_PATH
        self.data: dict[str, Any] = {"runs": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- ラン ---------------------------------------------------------------
    def create_run(self, business_name: str, overview: str) -> str:
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.data["runs"][run_id] = {
            "business_name": business_name,
            "overview": overview,
            "status": "running",
            "created_at": _now(),
            "run_page_id": None,
            "decision": None,
            "weighted_total": None,
            "agents": {},
        }
        (config.RUNS_DIR / run_id).mkdir(parents=True, exist_ok=True)
        self._save()
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.data["runs"][run_id]

    def set_run_field(self, run_id: str, **kw: Any) -> None:
        self.data["runs"][run_id].update(kw)
        self._save()

    def latest_runs(self, n: int) -> list[tuple[str, dict]]:
        items = sorted(
            self.data["runs"].items(), key=lambda kv: kv[1]["created_at"], reverse=True
        )
        return items[:n]

    # --- エージェント -------------------------------------------------------
    def agent_status(self, run_id: str, agent_id: str) -> str:
        return self.get_run(run_id)["agents"].get(agent_id, {}).get("status", "pending")

    def mark_running(self, run_id: str, agent_id: str, notion_page_id: str | None) -> None:
        a = self.get_run(run_id)["agents"].setdefault(agent_id, {})
        a.update(status="running", notion_page_id=notion_page_id, started_at=_now())
        self._save()

    def save_artifact(
        self,
        run_id: str,
        agent_id: str,
        body: str,
        structured: dict,
        cost_usd: float | None,
        version: int = 1,
    ) -> None:
        d = config.RUNS_DIR / run_id
        (d / f"{agent_id}.md").write_text(body, encoding="utf-8")
        (d / f"{agent_id}.json").write_text(
            json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        a = self.get_run(run_id)["agents"].setdefault(agent_id, {})
        a.update(
            status="done",
            version=version,
            summary=structured.get("summary", ""),
            cost_usd=cost_usd,
            finished_at=_now(),
        )
        self._save()

    def mark_failed(self, run_id: str, agent_id: str, err: str) -> None:
        a = self.get_run(run_id)["agents"].setdefault(agent_id, {})
        a.update(status="failed", error=err[:500], finished_at=_now())
        self.set_run_field(run_id, status="failed")

    def load_artifact(self, run_id: str, agent_id: str) -> tuple[str, dict]:
        d = config.RUNS_DIR / run_id
        body = (d / f"{agent_id}.md").read_text(encoding="utf-8")
        structured = json.loads((d / f"{agent_id}.json").read_text(encoding="utf-8"))
        return body, structured

    def page_id(self, run_id: str, agent_id: str) -> str | None:
        return self.get_run(run_id)["agents"].get(agent_id, {}).get("notion_page_id")

    def all_artifacts(self, run_id: str) -> dict[str, tuple[str, dict]]:
        out = {}
        for aid, a in self.get_run(run_id)["agents"].items():
            if a.get("status") == "done":
                out[aid] = self.load_artifact(run_id, aid)
        return out
