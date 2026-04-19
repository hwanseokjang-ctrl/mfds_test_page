"""제품명 분석 페이지의 입력/프로세스 스텝 정의."""

from __future__ import annotations

from common.llm_process import InputIndex, PageConfig, ProcessStep


PAGE_CONFIG: PageConfig = PageConfig(
    slug="product_name_analysis",
    title="제품명 분석",
    description=(
        "제품명과 원재료명을 입력받아 전처리로 제품명 토큰을 분류(A~G)하고, "
        "세분화 분석 6종을 LLM 으로 수행한 뒤 Python 패턴 로직으로 취합합니다."
    ),
    inputs=[
        InputIndex(
            key="product_name",
            label="제품명",
            placeholder="예: 16곡미숫가루",
            multiline=False,
            required=True,
        ),
        InputIndex(
            key="ingredients",
            label="원재료명",
            placeholder="쌀, 보리, 현미, 콩, 참깨, ...",
            multiline=True,
            required=True,
        ),
    ],
    steps=[
        ProcessStep(
            key="preprocess",
            label="전처리",
            description="제품명을 의미 단위로 분해하고 (A)~(G) 카테고리로 분류",
        ),
        ProcessStep(
            key="seg_1",
            label="세분화 1: 원재료명",
            description="제품명에 사용된 원재료명이 원재료 목록에 표시되었는지 확인",
        ),
        ProcessStep(
            key="seg_2",
            label="세분화 2: 통칭명(C)",
            description="통칭명(곡/고기/과일 등) 사용 시 해당 원재료의 목록 표시 여부 확인",
        ),
        ProcessStep(
            key="seg_3",
            label="세분화 3: 식품유형명·편의식품·요리명(D)",
            description="(D) 분류 명칭 사용 시 함량 표시 면제 규칙 적용 여부 판단",
        ),
        ProcessStep(
            key="seg_4",
            label="세분화 4: 추출물·농축액",
            description="추출물/농축액 형태 원재료의 원재료 목록 표시 준수 여부 확인",
        ),
        ProcessStep(
            key="seg_5",
            label="세분화 5: 성분명",
            description="제품명에 사용된 성분명이 원재료 목록에 표시되었는지 확인",
        ),
        ProcessStep(
            key="seg_6",
            label="세분화 6: 맛/향(E)",
            description="'○○향', '○○맛' 표현의 향료 단독 사용 및 표시 규정 준수 확인",
        ),
        ProcessStep(
            key="aggregate",
            label="취합 및 결론",
            description="6종 JSON 결과를 Python 패턴 로직으로 취합해 최종 텍스트 생성",
        ),
    ],
)
