from __future__ import annotations

import html
import json
from collections.abc import Iterator
from typing import Any, Callable

import streamlit as st

from common import llm_client
from common.llm_process import InputIndex, ProcessResult, ProcessStep, StepEvent


def render_llm_panel() -> None:
    """페이지 상단에 놓이는 LLM 설정 패널.

    - expander 라벨에 현재 ``provider · model`` 요약이 노출되어, 접혀 있어도
      어떤 조합으로 분석이 돌아가는지 한눈에 보인다.
    - 펼치면 provider / model 드롭다운과, 모델이 비추론 계열인 경우 temperature
      슬라이더가 나타난다.
    - 설정은 ``st.session_state`` 에 저장되어 페이지 간에 유지된다.
    """

    providers = llm_client.list_providers()
    active_provider = llm_client.get_active_provider()

    # 세션 기본값 주입 (최초 1회)
    st.session_state.setdefault(llm_client.SESSION_PROVIDER, active_provider.name)
    st.session_state.setdefault(
        llm_client.SESSION_MODEL,
        llm_client.get_active_model(active_provider),
    )
    st.session_state.setdefault(llm_client.SESSION_TEMPERATURE, 0.2)
    st.session_state.setdefault(llm_client.SESSION_TOP_P, 1.0)
    st.session_state.setdefault(llm_client.SESSION_REASONING_EFFORT, "low")

    with st.expander("⚙️ LLM 설정", expanded=False):
        _render_llm_panel_body(providers, active_provider)


def _render_llm_panel_body(
    providers: list[llm_client.ProviderInfo],
    active_provider: llm_client.ProviderInfo,
) -> None:
    selectable = [p for p in providers if p.available]
    unavailable = [p for p in providers if not p.available]
    selectable_names = [p.name for p in selectable]

    # 이전 선택이 현재 가능한 provider 목록에 없으면 보정
    if st.session_state.get(llm_client.SESSION_PROVIDER) not in selectable_names:
        st.session_state[llm_client.SESSION_PROVIDER] = selectable_names[0]

    col_prov, col_model = st.columns([1, 2])

    with col_prov:
        st.markdown("**제공자**")
        st.radio(
            "제공자",
            options=selectable_names,
            format_func=lambda n: next(p.display for p in selectable if p.name == n),
            key=llm_client.SESSION_PROVIDER,
            label_visibility="collapsed",
        )

    # radio 렌더 직후 session_state 가 현재값으로 동기화됨
    provider_info = llm_client.get_provider(st.session_state[llm_client.SESSION_PROVIDER])
    catalog = llm_client.list_models(provider_info.name)
    model_values = [m.value for m in catalog]

    # 모델 선택이 현재 provider 카탈로그와 맞지 않으면 default 로 리셋
    prior_model = st.session_state.get(llm_client.SESSION_MODEL)
    if prior_model not in model_values:
        st.session_state[llm_client.SESSION_MODEL] = (
            provider_info.default_model
            if provider_info.default_model in model_values
            else (model_values[0] if model_values else "-")
        )

    with col_model:
        st.markdown("**모델**")
        if not catalog:
            st.caption("선택 가능한 모델이 없습니다.")
        else:
            st.selectbox(
                "모델",
                options=model_values,
                format_func=lambda v: next(m.label for m in catalog if m.value == v),
                key=llm_client.SESSION_MODEL,
                label_visibility="collapsed",
            )

    chosen_model = st.session_state.get(llm_client.SESSION_MODEL, "-")

    spec = llm_client.get_model_spec(provider_info.name, chosen_model)

    st.divider()
    if provider_info.name == "placeholder":
        st.caption("⚠️ 실제 LLM 을 호출하지 않고 데모 placeholder 결과를 반환합니다.")
    elif spec.reasoning_style in ("effort", "thinking"):
        _render_effort_selector(spec)
    else:
        col_t, col_p = st.columns(2)
        with col_t:
            st.slider(
                "Temperature (낮을수록 결정적)",
                min_value=0.0,
                max_value=1.5,
                value=st.session_state.get(llm_client.SESSION_TEMPERATURE, 0.2),
                step=0.05,
                key=llm_client.SESSION_TEMPERATURE,
                help="0 에 가까울수록 같은 입력에 같은 응답을 낼 확률이 높아집니다.",
            )
        with col_p:
            st.slider(
                "Top-p (낮을수록 집중적)",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.get(llm_client.SESSION_TOP_P, 1.0),
                step=0.05,
                key=llm_client.SESSION_TOP_P,
                help="상위 누적 확률 내 토큰만 샘플링합니다. 1.0이면 모든 토큰 고려.",
            )

    if unavailable:
        with st.expander("미연결 제공자 안내", expanded=False):
            for p in unavailable:
                st.caption(f"• **{p.display}** — {p.hint}")


_EFFORT_OPTIONS: list[str] = ["none", "low", "medium", "high"]
_EFFORT_LABELS: dict[str, str] = {
    "none": "none (추론 끔)",
    "low": "low",
    "medium": "medium",
    "high": "high",
}


def _render_effort_selector(spec: llm_client.ModelSpec) -> None:
    """추론 강도(Reasoning effort) 라디오. OpenAI/Gemini 공통 UI."""

    if st.session_state.get(llm_client.SESSION_REASONING_EFFORT) not in _EFFORT_OPTIONS:
        st.session_state[llm_client.SESSION_REASONING_EFFORT] = "none"

    st.markdown("**추론 강도 (Reasoning Effort)**")
    st.radio(
        "추론 강도",
        options=_EFFORT_OPTIONS,
        format_func=lambda v: _EFFORT_LABELS[v],
        key=llm_client.SESSION_REASONING_EFFORT,
        horizontal=True,
        label_visibility="collapsed",
    )

    current = st.session_state.get(llm_client.SESSION_REASONING_EFFORT, "medium")
    if spec.reasoning_style == "thinking":
        budget = llm_client._GEMINI_THINKING_BUDGET.get(current, 0)
        if current == "none":
            st.caption("Gemini `thinking_budget = 0` — 추론 비활성.")
        else:
            st.caption(f"Gemini `thinking_budget ≈ {budget}` 토큰으로 전달됩니다.")
    else:  # "effort" (OpenAI)
        if current == "none":
            st.caption("OpenAI `reasoning_effort` 파라미터를 전달하지 않습니다.")
        else:
            st.caption(f"OpenAI `reasoning_effort = \"{current}\"` 로 전달됩니다.")


def render_prompt_editor(
    prompt_catalog: list,
    *,
    key_prefix: str = "",
) -> None:
    """페이지 프롬프트를 웹에서 직접 편집하는 패널.

    ``prompt_catalog`` 는 각 페이지의 ``prompts.PROMPT_CATALOG`` (``PromptSpec`` 리스트).
    편집 내용은 ``prompts.override_session_key(spec.key)`` 키로 session_state 에
    저장되며, ``prompts.get_template(key)`` 호출 시 자동으로 반영된다.
    새로고침 시 세션이 초기화되면 원본 템플릿으로 돌아간다.
    """

    if not prompt_catalog:
        return

    override_key = lambda spec: f"prompt_override__{spec.key}"  # noqa: E731

    modified_count = sum(
        1
        for spec in prompt_catalog
        if st.session_state.get(override_key(spec), spec.default) != spec.default
    )
    label = "📝 프롬프트 편집"
    if modified_count:
        label += f" — **{modified_count}개 수정됨**"

    with st.expander(label, expanded=False):
        st.caption(
            "각 프롬프트에 `{제품명}`, `{원재료명}`, `{PRE_out}` 자리표시자를 사용할 수 있습니다. "
            "실행 시 자동 치환됩니다. 편집 내용은 이번 세션 동안만 유지되며 새로고침 시 원본으로 돌아갑니다."
        )

        reset_all_key = f"{key_prefix}__prompt_reset_all"
        if st.button("↻ 모든 프롬프트 원본으로 되돌리기", key=reset_all_key):
            for spec in prompt_catalog:
                st.session_state.pop(override_key(spec), None)
            st.rerun()

        tabs = st.tabs([spec.short for spec in prompt_catalog])
        for tab, spec in zip(tabs, prompt_catalog):
            with tab:
                _render_single_prompt_editor(spec, key_prefix)


def _render_single_prompt_editor(spec, key_prefix: str) -> None:
    override_key = f"prompt_override__{spec.key}"
    reset_btn_key = f"{key_prefix}__prompt_reset__{spec.key}"

    # 리셋 버튼: textarea 렌더 전에 처리해야 session_state 를 수정할 수 있음
    if st.button("↻ 이 프롬프트만 원본으로", key=reset_btn_key):
        st.session_state.pop(override_key, None)

    # 최초 렌더 시 기본값 주입 (빈 문자열로 오염된 경우도 복구)
    if not st.session_state.get(override_key):
        st.session_state[override_key] = spec.default

    current_value: str = st.session_state[override_key]
    is_modified = current_value != spec.default

    # 자리표시자 누락 경고 (원본에 있던 것이 편집 후 사라졌으면)
    missing_placeholders: list[str] = []
    for ph in ("{제품명}", "{원재료명}", "{PRE_out}"):
        if ph in spec.default and ph not in current_value:
            missing_placeholders.append(ph)

    meta_bits: list[str] = [f"길이 {len(current_value):,}자"]
    if is_modified:
        meta_bits.append("**수정됨**")
    st.caption(f"{spec.label} · " + " · ".join(meta_bits))

    if missing_placeholders:
        st.warning(
            "원본에 있던 자리표시자가 누락되었습니다: "
            + ", ".join(f"`{p}`" for p in missing_placeholders)
            + " — 실행 시 해당 값이 프롬프트에 전달되지 않습니다."
        )

    st.text_area(
        spec.label,
        key=override_key,
        height=400,
        label_visibility="collapsed",
    )


def render_header(title: str, subtitle: str = "") -> None:
    """페이지 상단 타이틀 영역."""
    sub_html = f'<p class="page-sub">{html.escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="page-header">
            <h1 class="page-title">{html.escape(title)}</h1>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_input_form(
    indexes: list[InputIndex],
    key_prefix: str = "",
) -> tuple[dict[str, str], bool]:
    """입력 폼을 렌더하고 (inputs_dict, submitted) 를 반환합니다.

    - ``multiline`` 이면 ``st.text_area`` 로 렌더하고, 아니면 ``st.text_input``.
    - ``required`` 이면 라벨 끝에 * 표시.
    - ``key_prefix`` 로 여러 폼이 동일 페이지에 있을 때 키 충돌을 방지합니다.
    """
    form_key = f"{key_prefix or 'form'}__input_form"
    inputs: dict[str, str] = {}
    with st.form(form_key, clear_on_submit=False):
        st.markdown("#### 입력")
        for idx in indexes:
            label = f"{idx.label} *" if idx.required else idx.label
            widget_key = f"{key_prefix or 'form'}__{idx.key}"
            if idx.multiline:
                inputs[idx.key] = st.text_area(
                    label,
                    key=widget_key,
                    placeholder=idx.placeholder,
                    height=120,
                )
            else:
                inputs[idx.key] = st.text_input(
                    label,
                    key=widget_key,
                    placeholder=idx.placeholder,
                )
        col_left, col_right = st.columns([1, 4])
        with col_left:
            submitted = st.form_submit_button("분석 실행", type="primary")
        with col_right:
            st.caption("필수 입력(*)을 채운 뒤 분석을 실행하세요.")

    if submitted:
        missing = [i.label for i in indexes if i.required and not (inputs.get(i.key) or "").strip()]
        if missing:
            st.warning("다음 항목을 입력해주세요: " + ", ".join(missing))
            return inputs, False

    return inputs, submitted


def render_process_tracker(
    steps: list[ProcessStep],
    current_index: int = -1,
) -> None:
    """파이프라인 단계 시각화.

    - ``current_index == -1`` : 전체 대기
    - ``0 <= current_index < len(steps)`` : 해당 단계가 진행중, 앞 단계는 완료
    - ``current_index >= len(steps)`` : 전체 완료
    """
    if not steps:
        st.markdown('<div class="empty-hint">정의된 프로세스 단계가 없습니다.</div>', unsafe_allow_html=True)
        return

    pills: list[str] = []
    for i, step in enumerate(steps):
        if current_index < 0:
            css = ""
        elif i < current_index:
            css = "is-done"
        elif i == current_index:
            css = "is-active"
        else:
            css = ""
        pills.append(
            f'<span class="step-pill {css}" title="{html.escape(step.description)}">'
            f'<span class="step-index">{i + 1}</span>'
            f'{html.escape(step.label)}'
            f'</span>'
        )
    st.markdown('#### 파이프라인')
    st.markdown(f'<div class="step-row">{"".join(pills)}</div>', unsafe_allow_html=True)


def render_result_section(
    result: ProcessResult,
    steps: list[ProcessStep],
) -> None:
    """결과 영역. 최종 텍스트 + 단계별 중간 결과 expander."""
    st.markdown("#### 최종 결과")
    final_text = (result.final_text or "").strip()
    if final_text:
        st.markdown(final_text, unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="empty-hint">최종 텍스트가 비어있습니다.</div>',
            unsafe_allow_html=True,
        )

    if not result.intermediates:
        return

    st.markdown("#### 단계별 중간 결과")
    for step in steps:
        value = result.intermediates.get(step.key)
        if value is None:
            continue
        with st.expander(f"{step.label} — {step.description or ''}".strip(" —"), expanded=False):
            _render_intermediate_value(value)


def _render_intermediate_value(value: Any) -> None:
    if isinstance(value, (dict, list)):
        try:
            st.json(value)
            return
        except Exception:
            st.code(json.dumps(value, ensure_ascii=False, indent=2), language="json")
            return
    if isinstance(value, str):
        if "\n" in value or len(value) > 200:
            st.markdown(value, unsafe_allow_html=True)
        else:
            st.write(value)
        return
    st.write(value)


def render_live_execution(
    steps: list[ProcessStep],
    run_steps_fn: Callable[[dict[str, str]], Iterator[StepEvent]],
    inputs: dict[str, str],
) -> ProcessResult:
    """단계별 실행 UI.

    ``run_steps_fn(inputs)`` 가 yield 하는 ``StepEvent`` 를 하나씩 받아
    ``st.status`` 블록으로 시각화한다. 각 블록은 실행 중엔 펼쳐져서 전송된
    프롬프트와 응답을 보여주고, 완료되면 접힌다.

    반환값은 전체 단계를 모은 ``ProcessResult`` 이며 호출측이 최종 텍스트를
    별도 렌더하거나 저장하는 데 사용할 수 있다.
    """

    step_by_key = {s.key: s for s in steps}
    total = len(steps)
    collected: dict[str, Any] = {}
    final_text = ""

    st.markdown("#### 실행 과정")
    progress_bar = st.progress(0.0, text="실행 준비 중...")

    for idx, event in enumerate(run_steps_fn(inputs), start=1):
        step = step_by_key.get(event.step_key)
        label = step.label if step else event.step_key
        description = step.description if step else ""

        with st.status(
            f"[{idx}/{total}] {label} — 실행 중...",
            expanded=True,
            state="running",
        ) as status:
            if description:
                st.caption(description)
            if event.note:
                st.caption(f"ℹ️ {event.note}")

            if event.prompt is not None:
                with st.expander("🧾 전송 프롬프트 보기", expanded=False):
                    st.code(event.prompt, language="markdown")
            else:
                st.caption("— 이 단계는 LLM 호출이 아닙니다.")

            st.markdown("**응답 / 결과**")
            _render_intermediate_value(event.result)

            status.update(
                label=f"✅ [{idx}/{total}] {label} — 완료",
                state="complete",
                expanded=False,
            )

        progress_bar.progress(idx / total, text=f"{idx}/{total} 단계 완료")

        entry: dict[str, Any] = {"result": event.result}
        if event.prompt is not None:
            entry["prompt"] = event.prompt
        if event.note:
            entry["note"] = event.note
        collected[event.step_key] = entry
        if event.step_key == "aggregate" and isinstance(event.result, str):
            final_text = event.result

    progress_bar.empty()
    return ProcessResult(intermediates=collected, final_text=final_text)


def render_final_text(result: ProcessResult) -> None:
    """최종 텍스트 블록만 강조 렌더 (중간 결과는 ``render_live_execution`` 이 이미 보여줌)."""

    final_text = (result.final_text or "").strip()
    if not final_text:
        return
    st.markdown("#### 최종 결과")
    st.markdown(final_text, unsafe_allow_html=True)
