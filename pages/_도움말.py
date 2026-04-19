"""도움말 — 데모 개요 및 사용 안내.

``app.py`` 의 ``st.navigation`` 에서 "도움말" 섹션으로 노출된다.
기존 홈(app.py)이 제공하던 소개 카드/안내는 이 페이지로 이관되었다.
"""

from __future__ import annotations

import streamlit as st


st.markdown(
    """
    # 식약처 식품표시AI 분석 테스트 데모

    본 데모는 **식품표시AI** 과업의 LLM 기반 분석 결과를 실제 사용자 관점에서
    점검하기 위한 테스트 페이지입니다. 분석 항목별로 입력 → LLM 파이프라인
    (전처리 → 세분화 → 취합) → 결과 표시 구조로 구성되어 있습니다.
    """
)

st.divider()

st.subheader("사용 방법")
st.markdown(
    """
    1. 좌측 **사이드바**에서 분석 메뉴를 선택합니다.
    2. 페이지 상단 **⚙️ LLM 설정** 패널에서 사용할 제공자(GPT / Gemini)와 모델을 선택합니다.
       - `.env` 에 키가 등록된 제공자만 선택 가능합니다.
       - 키가 전혀 없으면 자동으로 "데모 Placeholder" 모드가 활성화되어 더미 결과를 보여줍니다.
    3. 입력 폼을 작성하고 **분석 실행** 버튼을 누릅니다.
    4. 각 단계가 순차적으로 실행되며 **전송 프롬프트**와 **JSON 응답**을 단계별로 확인할 수 있습니다.
    5. 마지막에 취합된 **최종 결과 텍스트**가 하단에 표시됩니다.
    """
)

st.subheader("새 분석 페이지 추가")
st.markdown(
    """
    1. `page_modules/_template/` 를 `page_modules/<새_slug>/` 로 복사
    2. 복사한 폴더의 `prd.md` 작성 → `config.py`(PAGE_CONFIG), `logic.py`(`run_steps`) 구현
    3. `pages/` 에 thin wrapper 추가 (예: `pages/2_원재료분석.py`)
    4. **`app.py` 의 `NAV_PAGES`** 에 `st.Page(...)` 한 줄 등록
       - 카테고리(예: "분석", "부가") 를 기준으로 배치
    """
)

st.subheader("LLM 연결")
st.markdown(
    """
    - `.env` 파일에 `OPENAI_API_KEY` 또는 `GOOGLE_API_KEY` 중 하나 이상 입력.
    - 모델명은 페이지 상단 LLM 설정 패널에서 선택(기본값은 `.env` 의 `OPENAI_MODEL` / `GEMINI_MODEL`).
    - 자세한 내용: `README.md` 의 "LLM 연결" 섹션 참고.
    """
)

with st.expander("아키텍처 문서"):
    st.markdown(
        """
        - `docs/ARCHITECTURE.md` — 폴더 구조 · API 계약 · 파이프라인 모델
        - `docs/DESIGN.md` — 컬러 팔레트 · 공통 컴포넌트 사용 가이드
        """
    )
