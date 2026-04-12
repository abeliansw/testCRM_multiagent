"""
BaseAgent: 모든 에이전트의 공통 Agentic Loop 구현
Claude API tool_use 패턴 기반
"""

import json
import sys
import io
from anthropic import Anthropic

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


class BaseAgent:
    """
    Agentic Loop를 구현하는 베이스 클래스.
    하위 클래스는 execute_tool()만 구현하면 됨.
    """

    def __init__(self, name: str, model: str, system_prompt: str, tools: list):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools
        self.client = Anthropic()

    def execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """도구 실행 — 하위 클래스에서 반드시 구현"""
        raise NotImplementedError(f"{self.name}: execute_tool() 미구현 — {tool_name}")

    def _log(self, msg: str) -> None:
        print(f"  [{self.name}] {msg}", flush=True)

    def run(self, prompt: str) -> str:
        """
        Agentic Loop 실행.
        stop_reason == 'end_turn' 이 될 때까지 tool_use 결과를 반복 처리.
        """
        messages = [{"role": "user", "content": prompt}]
        self._log("시작")

        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=self.system_prompt,
            messages=messages,
        )
        if self.tools:
            kwargs["tools"] = self.tools

        collected_text = []
        max_continuations = 5
        continuation_count = 0

        while True:
            response = self.client.messages.create(**kwargs)

            # 텍스트 블록 수집
            text_blocks = [b for b in response.content if b.type == "text"]
            tool_blocks = [b for b in response.content if b.type == "tool_use"]

            # 텍스트 실시간 출력 (있을 경우)
            for tb in text_blocks:
                if tb.text.strip():
                    print(tb.text, flush=True)
                    collected_text.append(tb.text)

            # ── 종료 조건 ──────────────────────────────────────
            if response.stop_reason == "end_turn":
                self._log("완료")
                return " ".join(collected_text).strip()

            # ── 토큰 한도 도달: 계속 생성 요청 ────────────────
            if response.stop_reason == "max_tokens":
                continuation_count += 1
                if continuation_count >= max_continuations:
                    self._log(f"max_tokens 한도({max_continuations}회) 도달 — 루프 종료")
                    break
                self._log(f"max_tokens 도달 — 계속 생성 요청 ({continuation_count}/{max_continuations})")
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": "계속 작성해주세요. 중단된 부분부터 이어서 완성해주세요."})
                kwargs["messages"] = messages
                continue

            # ── 도구 실행 ──────────────────────────────────────
            if response.stop_reason == "tool_use" and tool_blocks:
                tool_results = []
                for block in tool_blocks:
                    self._log(f"도구 호출: {block.name}({list(block.input.keys())})")
                    try:
                        result = self.execute_tool(block.name, block.input)
                        content = json.dumps(result, ensure_ascii=False, indent=2)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content,
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": str(e)}, ensure_ascii=False),
                            "is_error": True,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                kwargs["messages"] = messages
            else:
                # 예기치 않은 stop_reason
                self._log(f"예기치 않은 stop_reason: {response.stop_reason}")
                break

        return " ".join(collected_text).strip()
