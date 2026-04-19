# 디자인 가이드

## 원칙
- **정보 중심**: LLM 분석 과정을 한 화면에서 따라갈 수 있도록 입력 → 파이프라인 → 결과를 세로로 정렬한다.
- **브랜드 톤**: 식약처/식품 도메인 → 녹색 계열. 과한 장식 없이 절제된 light 테마.
- **가독성 우선**: 본문은 sans-serif 기본, 좁은 열 폭을 피해 `layout="wide"` 를 사용한다.

## 컬러 팔레트

| 용도 | HEX |
| --- | --- |
| primaryColor (브랜드/강조) | `#2E7D32` |
| accent (진행중 하이라이트) | `#66BB6A` |
| primary soft (배경/완료 pill) | `#E8F3EA` |
| backgroundColor | `#FFFFFF` |
| secondaryBackgroundColor (사이드바) | `#F1F8F2` |
| textColor (본문) | `#1F2937` |
| muted (보조 텍스트) | `#6B7280` |
| border-soft (구분선) | `#D7E4DA` |

위 값은 `.streamlit/config.toml` 과 `common/layout.py` 의 CSS 변수(`--brand-primary` 등) 두 곳에 동일하게 들어가 있습니다. 변경 시 두 파일을 함께 수정하세요.

## 공통 컴포넌트 사용 가이드

| 함수 | 위치 | 용도 |
| --- | --- | --- |
| `apply_page_config(title, icon)` | `common/layout.py` | 페이지 최상단 1회. `set_page_config` + 공통 CSS 주입 |
| `render_sidebar_brand()` | `common/layout.py` | 사이드바 상단 브랜드 블록 |
| `render_header(title, subtitle)` | `common/components.py` | 본문 상단 타이틀 영역 |
| `render_input_form(indexes, key_prefix)` | `common/components.py` | 입력 폼 + 제출 버튼. `(inputs, submitted)` 반환 |
| `render_process_tracker(steps, current_index)` | `common/components.py` | 파이프라인 단계 pill. `-1` = 대기, `len(steps)` = 전체 완료 |
| `render_result_section(result, steps)` | `common/components.py` | 최종 텍스트 + 단계별 중간 결과 expander |

## 새 페이지에서 레이아웃 재사용하는 법

```python
import streamlit as st
from common.layout import apply_page_config, render_sidebar_brand
from common.components import (
    render_header, render_input_form, render_process_tracker,
    render_live_execution, render_final_text,
)
from common.page_loader import load_page_module

apply_page_config()
render_sidebar_brand()

config, _run, run_steps = load_page_module("<your_page_module>")
render_header(config.title, config.description)

inputs, submitted = render_input_form(config.inputs, key_prefix=config.slug)
if submitted:
    render_process_tracker(config.steps, current_index=0)
    result = render_live_execution(config.steps, run_steps, inputs)
    render_process_tracker(config.steps, current_index=len(config.steps))
    render_final_text(result)
else:
    render_process_tracker(config.steps, current_index=-1)
```

## 프로세스 트래커 상태 규칙

- `current_index = -1` : 모든 단계 대기 (회색)
- `current_index = i (0..len-1)` : `0..i-1` 완료(녹색), `i` 진행중(테두리 강조), 그 이후 대기
- `current_index >= len(steps)` : 전체 완료 (전부 녹색)

데모 단계에서는 동기 실행이므로 제출 직후 `len(steps)` 로 호출해 "전체 완료" 상태를 표시합니다. 추후 비동기/스트리밍을 도입하면 단계별 업데이트가 가능합니다.
