"""
페이지 설정 템플릿.

사용법:
    1. 이 폴더(page_modules/_template) 전체를 복사해서
       page_modules/<새_페이지_slug>/ 로 이름을 바꿉니다.
    2. 아래 PAGE_CONFIG 를 해당 페이지 PRD 에 맞게 채웁니다.
    3. logic.py 에서 run() 을 구현합니다.

이 파일은 반드시 `PAGE_CONFIG: PageConfig` 를 export 해야 합니다.
공통 프레임워크(common/page_loader.py)가 이 값을 읽어 입력폼과
진행 단계 UI 를 자동으로 렌더합니다.
"""

from common.llm_process import InputIndex, PageConfig, ProcessStep


PAGE_CONFIG = PageConfig(
    # slug: URL/폴더 식별자. page_modules 하위 폴더명과 일치시킬 것.
    slug="_template",

    # title: 페이지 상단에 표시될 제목.
    title="<페이지 제목>",

    # description: 페이지 상단 설명 텍스트.
    description="<이 페이지가 무엇을 분석하는지 한 줄 설명>",

    # inputs: 사용자가 입력할 index 목록.
    #   - key: run(inputs) dict 의 key 로 전달됨.
    #   - multiline: 여러 줄 입력이면 True.
    inputs=[
        InputIndex(
            key="example_key",
            label="예시 입력",
            placeholder="여기에 텍스트를 입력하세요",
            multiline=False,
            required=True,
        ),
    ],

    # steps: 파이프라인 단계 목록. 화면에 단계별 진행/결과가 표시됨.
    #   - key: ProcessResult.intermediates 의 key 와 매칭.
    #   - 전처리 > 세분화 > 최종 > 취합 순서로 나열.
    steps=[
        ProcessStep(key="preprocess", label="전처리", description="입력 정제"),
        ProcessStep(key="final", label="최종 분석", description="통합 판단"),
        ProcessStep(key="aggregate", label="취합/결론", description="결론 텍스트 생성"),
    ],
)
