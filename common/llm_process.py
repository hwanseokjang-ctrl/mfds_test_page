"""LLM 프로세스 공통 계약 모듈.

각 분석 페이지가 공통으로 사용하는 입력/프로세스/결과 데이터 모델과,
페이지별 logic 함수의 시그니처(LogicRunner), 그리고 실행 래퍼(run_pipeline)를 정의한다.
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field


class InputIndex(BaseModel):
    """사용자 입력 단위 하나(한 필드)를 설명한다."""

    key: str
    label: str
    placeholder: str = ""
    multiline: bool = False
    required: bool = True


class ProcessStep(BaseModel):
    """LLM 파이프라인의 한 단계를 설명한다."""

    key: str
    label: str
    description: str = ""


class PageConfig(BaseModel):
    """분석 페이지 1개의 메타 정보(입력/단계/설명)."""

    slug: str
    title: str
    description: str
    inputs: list[InputIndex]
    steps: list[ProcessStep]


class ProcessResult(BaseModel):
    """페이지 logic.run() 이 반환해야 하는 결과 구조.

    intermediates 는 step.key -> 중간 결과(임의 타입) 매핑이며,
    final_text 는 최종 취합된 한국어 텍스트 결과이다.
    """

    intermediates: dict[str, Any] = Field(default_factory=dict)
    final_text: str = ""


class StepEvent(BaseModel):
    """파이프라인 한 단계의 실행 이벤트.

    ``run_steps()`` 가 단계마다 하나씩 yield 하는 단위.
    UI 는 이 이벤트를 받아 전송 프롬프트/응답/설명을 라이브로 렌더한다.
    """

    step_key: str
    prompt: str | None = None  # 이 단계에서 LLM 에 전송된(될) 프롬프트. Python 로직 단계는 None
    result: Any = None  # 이 단계의 응답(LLM JSON, 텍스트, 딕셔너리 등)
    note: str = ""  # 보조 설명 (예: "Python 패턴 매칭으로 취합")


# 각 page_modules.<name>.logic 모듈이 반드시 제공해야 하는 run 함수 타입.
LogicRunner = Callable[[dict[str, str]], ProcessResult]
# 선택적으로 제공 가능한 step-by-step 실행 타입.
StepRunner = Callable[[dict[str, str]], "Iterator[StepEvent]"]


# 순환 import 회피용 late import 힌트 (타입체커가 런타임 eval 하지 않도록).
from typing import Iterator  # noqa: E402


def run_pipeline(
    config: PageConfig,
    inputs: dict[str, str],
    runner: LogicRunner,
) -> ProcessResult:
    """페이지 logic 실행 래퍼.

    - 필수 입력 누락 시 ValueError.
    - runner 실행 중 예외 발생 시 ProcessResult 에 에러 메시지를 담아 반환.
    """

    missing = [idx.key for idx in config.inputs if idx.required and not inputs.get(idx.key)]
    if missing:
        raise ValueError(f"필수 입력이 누락되었습니다: {', '.join(missing)}")

    try:
        return runner(inputs)
    except Exception as exc:  # noqa: BLE001 - 데모 환경에서는 사용자에게 노출
        return ProcessResult(
            intermediates={"error": f"{type(exc).__name__}: {exc}"},
            final_text=f"분석 중 오류가 발생했습니다: {exc}",
        )
