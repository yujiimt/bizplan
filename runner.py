"""エージェント実行アダプタ。

SDK 依存はこの1ファイルに閉じ込める（バージョン差異が出たらここだけ直す）。
本番は SdkRunner、テスト/ドライランは StubRunner。両者とも run() で
(本文+STRUCTURED を含む生テキスト, cost_usd) を返す。
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass

from . import config


@dataclass
class AgentResult:
    text: str
    cost_usd: float | None


class SdkRunner:
    """claude-agent-sdk 経由で1エージェントを実行する。"""

    def run(self, *, system_prompt: str, user_prompt: str, model: str, web: bool) -> AgentResult:
        return asyncio.run(
            self._run_async(system_prompt=system_prompt, user_prompt=user_prompt,
                            model=model, web=web)
        )

    async def _run_async(self, *, system_prompt, user_prompt, model, web) -> AgentResult:
        # 遅延 import（スタブ運用時に SDK 未導入でも動くように）
        from claude_agent_sdk import (
            query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock,
        )

        if web:
            # WebSearch を使える分析エージェント。ファイル編集系は禁止。
            # NOTE: 「WebSearch だけ露出」の正確な指定は SDK バージョンで揺れる。
            #       期待挙動と違えば allowed_tools / tools / disallowed_tools を調整する。
            options = ClaudeAgentOptions(
                system_prompt=system_prompt,
                model=model,
                tools={"type": "preset", "preset": "claude_code"},
                allowed_tools=["WebSearch", "WebFetch"],
                disallowed_tools=[
                    "Bash", "Write", "Edit", "Read", "NotebookEdit",
                    "Glob", "Grep", "KillBash", "BashOutput",
                ],
                permission_mode="bypassPermissions",
                max_turns=config.WEB_MAX_TURNS,
            )
        else:
            # 純分析（ツール無し・単発生成）
            options = ClaudeAgentOptions(system_prompt=system_prompt, model=model)

        parts: list[str] = []
        final: str | None = None
        cost: float | None = None
        async for msg in query(prompt=user_prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        parts.append(b.text)
            elif isinstance(msg, ResultMessage):
                cost = msg.total_cost_usd
                if msg.result:
                    final = msg.result
        return AgentResult(text=(final or "".join(parts)).strip(), cost_usd=cost)


class StubRunner:
    """API を一切叩かずに、役割別の擬似アーティファクトを返す（ドライラン用）。"""

    def __init__(self) -> None:
        from . import _fixtures
        self._fixtures = _fixtures.ARTIFACTS

    def run(self, *, system_prompt: str, user_prompt: str, model: str, web: bool) -> AgentResult:
        agent_id = "ceo"
        for aid in self._fixtures:
            if f"[AGENT:{aid}]" in user_prompt:
                agent_id = aid
                break
        return AgentResult(text=self._fixtures[agent_id], cost_usd=0.0123)


def get_runner(dry_run: bool):
    return StubRunner() if dry_run else SdkRunner()
