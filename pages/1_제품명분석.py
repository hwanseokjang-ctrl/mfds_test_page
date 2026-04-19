"""제품명 분석 페이지 (thin wrapper).

실제 입력 스펙·프로세스 단계·프롬프트·로직은 ``page_modules.product_name_analysis``
에 정의되어 있으며, 이 파일은 공통 레이아웃/컴포넌트를 조립하는 역할만 담당한다.

``st.set_page_config`` 와 사이드바 조립은 엔트리(``app.py``)가 담당하므로
이 파일에서는 호출하지 않는다.
"""

from __future__ import annotations

import streamlit as st

from common.components import (
    render_final_text,
    render_header,
    render_input_form,
    render_live_execution,
    render_llm_panel,
    render_process_tracker,
    render_prompt_editor,
)
from common.page_loader import load_page_module
from page_modules.product_name_analysis import prompts as pna_prompts


MODULE_NAME = "product_name_analysis"


config, _run, run_steps = load_page_module(MODULE_NAME)

render_header(config.title, config.description)
render_llm_panel()
render_prompt_editor(pna_prompts.PROMPT_CATALOG, key_prefix=config.slug)

inputs, submitted = render_input_form(config.inputs, key_prefix=config.slug)

if not submitted:
    render_process_tracker(config.steps, current_index=-1)
    st.info("입력을 작성하고 **분석 실행** 버튼을 누르면 각 단계가 순차적으로 실행됩니다.")
else:
    render_process_tracker(config.steps, current_index=0)
    try:
        result = render_live_execution(config.steps, run_steps, inputs)
    except Exception as exc:  # noqa: BLE001 - 데모에서는 사용자에게 노출
        st.error(f"분석 중 오류가 발생했습니다: {type(exc).__name__}: {exc}")
    else:
        render_process_tracker(config.steps, current_index=len(config.steps))
        render_final_text(result)
