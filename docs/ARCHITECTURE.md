# 아키텍처 문서

## 개요

본 프로젝트는 식약처 식품표시AI 과업에서 사용할 LLM 분석 파이프라인들을 **테스트/시연**하기 위한 데모페이지입니다.
Python 기반 LLM 코드와 즉시 붙일 수 있고, 멀티페이지/입력폼/중간결과 렌더링을 빠르게 구현할 수 있어 **Streamlit** 을 채택했습니다.

분석 항목마다 입력 index, 프로세스 단계, 결과 구조가 서로 다르므로, **공통 프레임워크(common/)** 와 **개별 페이지 구현(page_modules/)** 을 분리했습니다.
공통 프레임워크는 "입력폼 렌더링 → 파이프라인 단계별 진행 표시 → 중간/최종 결과 뷰어"까지의 틀을 담당하고,
각 페이지 구현은 "입력 정의(PageConfig)" 와 "파이프라인 실행(run)" 두 가지만 제공하면 됩니다.
이 분리로 공통 UX 를 깨지 않으면서 각 페이지는 독립적으로 개발/테스트 가능합니다.

## 구성 요소

- `common/llm_process.py` : 페이지 간 공통으로 쓰는 **데이터 모델**과 타입 정의.
- `common/layout.py` / `common/components.py` : 공통 UI.
- `common/page_loader.py` : `page_modules/<slug>` 의 `config`/`logic` 을 로드해서 화면을 렌더하는 진입점.
- `pages/N_<이름>.py` : Streamlit 멀티페이지 규약을 위한 얇은 wrapper. 실제 로직은 `page_modules/` 에 둡니다.
- `page_modules/<slug>/` : 페이지별 구현. `prd.md`, `config.py`, `logic.py` 를 포함합니다.

## 공통 API 계약

모든 페이지는 아래 계약을 따릅니다. 이 계약만 맞추면 공통 프레임워크가 입력폼/진행표시/결과뷰어를 자동으로 처리합니다.

```python
# common/llm_process.py
from pydantic import BaseModel
from typing import Any


class InputIndex(BaseModel):
    """입력 index 하나를 정의 (제품명, 원재료명 등)."""
    key: str              # 내부 식별자. run() 의 inputs dict key 와 동일.
    label: str            # 화면에 노출될 라벨.
    placeholder: str = "" # 입력창 placeholder.
    multiline: bool = False  # 여러 줄 입력이면 True.
    required: bool = True


class ProcessStep(BaseModel):
    """파이프라인 한 단계 (전처리/세분화/최종/취합 등)."""
    key: str              # intermediates dict 의 key 와 매칭.
    label: str            # 화면에 노출될 단계명.
    description: str = "" # 단계 설명 (툴팁/안내용).


class PageConfig(BaseModel):
    slug: str                # URL/폴더 식별자.
    title: str               # 페이지 상단 제목.
    description: str         # 페이지 설명.
    inputs: list[InputIndex] # 입력 index 목록.
    steps: list[ProcessStep] # 파이프라인 단계 목록.


class ProcessResult(BaseModel):
    intermediates: dict[str, Any] = {}  # 단계별 중간 결과 (key = ProcessStep.key).
    final_text: str = ""                # 취합된 최종 결론 텍스트.
```

각 페이지 모듈은 다음을 export 합니다.

- `page_modules/<slug>/config.py` : `PAGE_CONFIG: PageConfig`
- `page_modules/<slug>/logic.py`  : `def run(inputs: dict[str, str]) -> ProcessResult`

## 파이프라인 단계 모델

PRD 에서 정의한 LLM 프로세스는 다음 4단계입니다.

1. **전처리 (preprocess)** — 입력 텍스트 정제/정규화.
2. **세분화 분석 (segmented)** — 여러 하위 분석을 병렬/순차로 수행. 분석에 따라 생략 가능.
3. **최종 분석 (final)** — 세분화 결과를 바탕으로 한 통합 판단. 분석에 따라 생략 가능.
4. **취합/결론 (aggregate)** — 최종 결론 텍스트 생성.

각 단계는 `ProcessStep` 하나 (또는 세분화 처럼 여러 개) 로 표현되며, `ProcessResult.intermediates[step.key]` 로 중간 결과를 노출합니다.
공통 프레임워크는 `PageConfig.steps` 순서대로 진행상황 UI 를 렌더하고, `intermediates` 에 담긴 값을 해당 단계 섹션에 표시합니다.
최종 텍스트는 `final_text` 에서 가져와 상단/별도 섹션에 크게 표시합니다.

예시 (제품명 분석, 세분화 6종 + 최종 취합):

```python
PAGE_CONFIG = PageConfig(
    slug="product_name_analysis",
    title="제품명 분석",
    description="제품명과 원재료명을 입력받아 6종 세분화 분석 후 결론 텍스트를 생성합니다.",
    inputs=[
        InputIndex(key="product_name", label="제품명"),
        InputIndex(key="ingredients", label="원재료명", multiline=True),
    ],
    steps=[
        ProcessStep(key="preprocess", label="전처리"),
        ProcessStep(key="seg_1", label="세분화 분석 1"),
        ProcessStep(key="seg_2", label="세분화 분석 2"),
        ProcessStep(key="seg_3", label="세분화 분석 3"),
        ProcessStep(key="seg_4", label="세분화 분석 4"),
        ProcessStep(key="seg_5", label="세분화 분석 5"),
        ProcessStep(key="seg_6", label="세분화 분석 6"),
        ProcessStep(key="aggregate", label="취합/결론"),
    ],
)
```

## 개발 규칙

- 페이지별 폴더는 **독립적**으로 개발 가능해야 하며, 타 페이지 모듈을 직접 import 하지 않습니다.
- 공통 유틸이 필요하면 `common/` 에 추가합니다.
- 각 페이지 폴더의 `prd.md` 가 단일 진실 공급원 (single source of truth) 입니다. 구현 전에 반드시 PRD 를 먼저 작성/검토합니다.
