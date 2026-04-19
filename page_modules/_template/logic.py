"""페이지 로직 템플릿.

필수: ``run(inputs) -> ProcessResult``
선택(권장): ``run_steps(inputs) -> Iterator[StepEvent]``

- ``run_steps`` 를 구현하면 페이지 UI 가 각 단계를 ``st.status`` 로 라이브 렌더하여
  전송 프롬프트와 응답을 순차적으로 보여줍니다(데모 체감 ↑).
- ``run`` 만 구현해도 동작합니다. 그 경우 프레임워크가 결과를 한 번에 합성해 표시합니다.

구현 가이드
    전처리 → 세분화 분석 → 최종 분석 → 취합/결론 의 각 단계에서 StepEvent 를 yield 하세요.
    각 이벤트는 step_key (config.py 의 ProcessStep.key 와 동일) + 선택적 prompt + 결과를 담습니다.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from common.llm_process import ProcessResult, StepEvent


def run_steps(inputs: dict[str, str]) -> Iterator[StepEvent]:
    """단계별 실행 (권장).

    예시::

        prompt = format_preprocess_prompt(inputs)
        pre = call_llm(prompt)
        yield StepEvent(step_key="preprocess", prompt=prompt, result=pre)

        ...

        final_text = aggregate_python(seg_results)
        yield StepEvent(
            step_key="aggregate",
            prompt=None,
            result=final_text,
            note="Python 로직으로 취합",
        )
    """

    raise NotImplementedError("run_steps() 를 구현하세요.")
    if False:  # pragma: no cover - 타입 힌트 유지용
        yield StepEvent(step_key="")


def run(inputs: dict[str, str]) -> ProcessResult:
    """단일 호출 API. 일반적으로 ``run_steps`` 를 합쳐 반환하면 됩니다."""

    intermediates: dict[str, Any] = {}
    final_text = ""
    for event in run_steps(inputs):
        entry: dict[str, Any] = {"result": event.result}
        if event.prompt is not None:
            entry["prompt"] = event.prompt
        if event.note:
            entry["note"] = event.note
        intermediates[event.step_key] = entry
        if event.step_key == "aggregate" and isinstance(event.result, str):
            final_text = event.result
    return ProcessResult(intermediates=intermediates, final_text=final_text)
