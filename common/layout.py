from __future__ import annotations

import streamlit as st

_BASE_CSS = """
<style>
:root {
    --brand-primary: #2E7D32;
    --brand-primary-soft: #E8F3EA;
    --brand-accent: #66BB6A;
    --ink-strong: #1F2937;
    --ink-muted: #6B7280;
    --surface-muted: #F1F8F2;
    --border-soft: #D7E4DA;
}

section[data-testid="stSidebar"] {
    background-color: var(--surface-muted);
}

.brand-block {
    padding: 0.75rem 0.25rem 1.25rem 0.25rem;
    border-bottom: 1px solid var(--border-soft);
    margin-bottom: 1rem;
}
.brand-block .brand-logo {
    font-size: 1.6rem;
    margin-right: 0.35rem;
}
.brand-block .brand-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--brand-primary);
}
.brand-block .brand-sub {
    font-size: 0.78rem;
    color: var(--ink-muted);
    margin-top: 0.2rem;
    line-height: 1.35;
}

.page-header {
    padding: 0.25rem 0 1rem 0;
    border-bottom: 1px solid var(--border-soft);
    margin-bottom: 1.25rem;
}
.page-header .page-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--ink-strong);
    margin: 0;
}
.page-header .page-sub {
    font-size: 0.95rem;
    color: var(--ink-muted);
    margin-top: 0.35rem;
    line-height: 1.5;
}

.step-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.5rem 0 1rem 0;
}
.step-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.45rem 0.8rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 500;
    border: 1px solid var(--border-soft);
    background: #FFFFFF;
    color: var(--ink-muted);
    white-space: nowrap;
}
.step-pill .step-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 999px;
    font-size: 0.72rem;
    background: #E5E7EB;
    color: #4B5563;
}
.step-pill.is-done {
    background: var(--brand-primary-soft);
    border-color: var(--brand-accent);
    color: var(--brand-primary);
}
.step-pill.is-done .step-index {
    background: var(--brand-primary);
    color: #FFFFFF;
}
.step-pill.is-active {
    background: #FFFFFF;
    border-color: var(--brand-primary);
    color: var(--brand-primary);
    box-shadow: 0 0 0 2px var(--brand-primary-soft);
}
.step-pill.is-active .step-index {
    background: var(--brand-accent);
    color: #FFFFFF;
}

.final-result {
    padding: 1rem 1.1rem;
    border-radius: 10px;
    background: var(--brand-primary-soft);
    border-left: 4px solid var(--brand-primary);
    line-height: 1.6;
    color: var(--ink-strong);
}

.empty-hint {
    color: var(--ink-muted);
    font-size: 0.9rem;
    padding: 0.4rem 0;
}
</style>
"""


def apply_page_config(title: str = "식품표시AI 테스트", icon: str = "🥗") -> None:
    """Streamlit 페이지 기본 설정과 공통 CSS 를 주입합니다.

    각 페이지 최상단에서 한 번만 호출하세요.
    """
    st.set_page_config(
        page_title=title,
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_BASE_CSS, unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    """사이드바 상단에 프로젝트 브랜드 블록을 렌더합니다."""
    with st.sidebar:
        st.markdown(
            """
            <div class="brand-block">
                <div>
                    <span class="brand-logo">🥗</span>
                    <span class="brand-title">식품표시AI 테스트</span>
                </div>
                <div class="brand-sub">
                    식약처 식품표시AI 과업의<br/>
                    LLM 분석 결과를 탭 단위로 확인합니다.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("분석 항목을 선택하세요 ↓")


# 사이드바의 LLM 선택기는 제거되었습니다.
# LLM 설정은 각 분석 페이지 상단의 ``render_llm_panel()`` 에서 인라인으로 제공합니다.
