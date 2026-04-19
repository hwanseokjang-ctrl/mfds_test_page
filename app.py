"""식약처 식품표시AI LLM 분석 테스트 데모 — 엔트리.

``st.navigation`` 을 사용해 분석 페이지를 카테고리로 그룹핑한다. 분석 탭이
늘어나면 아래 ``NAV_PAGES`` dict 에 ``st.Page(...)`` 한 줄씩 추가하면 된다.

이 엔트리 파일에서 ``apply_page_config`` 와 ``render_sidebar_brand`` 를 한 번씩
호출하고, 선택된 서브 페이지는 ``pages/`` 아래 파일이 그대로 렌더한다. 따라서
각 서브 페이지는 더 이상 ``apply_page_config`` / 사이드바 조립 코드를 갖지 않는다.
"""

from __future__ import annotations

import streamlit as st

from common.layout import apply_page_config


apply_page_config()


# 네비게이션 트리. 섹션(key) 단위로 그룹핑되어 사이드바에 소제목과 함께 나열된다.
# 새 분석 페이지 추가 시 이 dict 에 st.Page(...) 를 등록하면 자동으로 메뉴에 반영된다.
NAV_PAGES: dict[str, list[st.Page]] = {
    "제품명 분석": [
        st.Page(
            "pages/1_제품명분석.py",
            title="단건 분석",
            icon="🔍",
            default=True,
        ),
        st.Page(
            "pages/2_배치분석.py",
            title="배치 분석",
            icon="📊",
        ),
    ],
    "도움말": [
        st.Page(
            "pages/_도움말.py",
            title="사용 안내",
            icon="📖",
        ),
    ],
}


st.navigation(NAV_PAGES).run()
