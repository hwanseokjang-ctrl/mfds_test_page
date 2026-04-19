"""페이지 모듈 동적 로더.

``page_modules.<module_name>`` 패키지에서 PAGE_CONFIG / run / run_steps 를
importlib 로 로드하여 반환한다. ``run_steps`` 는 선택 사항이며, 없으면
``run`` 결과를 한 번에 래핑한 단일 이벤트 시퀀스를 합성해 반환한다.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Callable

from common.llm_process import PageConfig, ProcessResult, StepEvent


LogicRun = Callable[[dict[str, str]], ProcessResult]
LogicRunSteps = Callable[[dict[str, str]], Iterator[StepEvent]]


def load_page_module(
    module_name: str,
) -> tuple[PageConfig, LogicRun, LogicRunSteps]:
    """지정한 페이지 모듈을 로드한다.

    Returns:
        ``(PAGE_CONFIG, run, run_steps)`` 튜플. ``run_steps`` 는 페이지가
        직접 구현했으면 그대로, 아니면 ``run`` 결과를 마지막에 한 번 yield 하는
        합성 이터레이터로 반환된다.
    """

    config_path = f"page_modules.{module_name}.config"
    logic_path = f"page_modules.{module_name}.logic"

    try:
        config_module = importlib.import_module(config_path)
    except ModuleNotFoundError as exc:
        raise ImportError(
            f"페이지 설정 모듈을 찾을 수 없습니다: '{config_path}'. "
            f"page_modules/{module_name}/config.py 가 존재하는지 확인하세요."
        ) from exc

    try:
        logic_module = importlib.import_module(logic_path)
    except ModuleNotFoundError as exc:
        raise ImportError(
            f"페이지 로직 모듈을 찾을 수 없습니다: '{logic_path}'. "
            f"page_modules/{module_name}/logic.py 가 존재하는지 확인하세요."
        ) from exc

    if not hasattr(config_module, "PAGE_CONFIG"):
        raise ImportError(f"'{config_path}' 에 PAGE_CONFIG 상수가 정의되어 있지 않습니다.")
    if not hasattr(logic_module, "run"):
        raise ImportError(f"'{logic_path}' 에 run(inputs) 함수가 정의되어 있지 않습니다.")

    page_config: PageConfig = config_module.PAGE_CONFIG
    run_fn: LogicRun = logic_module.run
    run_steps_fn: LogicRunSteps

    if hasattr(logic_module, "run_steps"):
        run_steps_fn = logic_module.run_steps
    else:
        run_steps_fn = _synthesize_run_steps(run_fn)

    if not isinstance(page_config, PageConfig):
        raise ImportError(
            f"'{config_path}.PAGE_CONFIG' 는 PageConfig 인스턴스여야 합니다. "
            f"현재 타입: {type(page_config).__name__}"
        )

    return page_config, run_fn, run_steps_fn


def _synthesize_run_steps(run_fn: LogicRun) -> LogicRunSteps:
    """``run_steps`` 를 구현하지 않은 페이지를 위해, ``run()`` 결과를
    intermediates 순서대로 풀어 단계별 이벤트 시퀀스로 변환한다."""

    def _iter(inputs: dict[str, str]) -> Iterator[StepEvent]:
        result = run_fn(inputs)
        for key, value in result.intermediates.items():
            if isinstance(value, dict) and ("prompt" in value or "result" in value):
                yield StepEvent(
                    step_key=key,
                    prompt=value.get("prompt"),
                    result=value.get("result"),
                    note=value.get("note", ""),
                )
            else:
                yield StepEvent(step_key=key, prompt=None, result=value)
        if result.final_text and "aggregate" not in result.intermediates:
            yield StepEvent(step_key="aggregate", prompt=None, result=result.final_text)

    return _iter
