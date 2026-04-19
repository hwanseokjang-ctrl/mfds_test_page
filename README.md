# 식약처 식품표시AI LLM 분석 테스트 데모

식약처 식품표시AI 과업의 LLM 분석 결과를 테스트하기 위한 Streamlit 기반 데모페이지입니다.
분석 항목마다 입력 → LLM 파이프라인(전처리 > 세분화 > 최종 > 취합) → 결과 표시 구조를 가지며, 항목별로 메뉴가 추가됩니다.

## 폴더 구조

```
mfds_test_page/
├── app.py                     # 홈/랜딩 페이지
├── requirements.txt           # 의존성 정의
├── .streamlit/config.toml     # Streamlit 테마 설정
├── common/                    # 공통 프레임워크
│   ├── layout.py              # 공통 레이아웃 (헤더, 사이드바 등)
│   ├── components.py          # 재사용 UI 컴포넌트 (입력폼, 중간결과 뷰어 등)
│   ├── llm_process.py         # 공통 데이터 모델(PageConfig/ProcessResult 등)
│   └── page_loader.py         # page_modules 로딩/실행 유틸
├── pages/                     # Streamlit 자동 메뉴 (thin wrapper)
│   └── 1_제품명분석.py          # page_modules/product_name_analysis 를 호출
├── page_modules/              # 각 분석 페이지의 실제 구현
│   ├── _template/             # 새 페이지를 만들 때 복사해서 쓰는 템플릿
│   │   ├── prd.md
│   │   ├── config.py
│   │   └── logic.py
│   └── product_name_analysis/ # 예시: 제품명 분석 페이지
│       ├── prd.md
│       ├── config.py
│       └── logic.py
└── docs/
    ├── ARCHITECTURE.md        # 아키텍처/API 계약 문서
    └── DESIGN.md              # 디자인 가이드
```

### 각 폴더의 역할

- **common/**: 모든 페이지가 공통으로 쓰는 프레임워크. 레이아웃, 컴포넌트, 데이터 모델, 로더를 제공합니다.
- **pages/**: Streamlit 의 멀티페이지 규약에 맞추는 얇은 wrapper만 둡니다. 실제 로직은 두지 않습니다.
- **page_modules/**: 페이지별 실제 구현. 각 폴더는 독립적으로 개발 가능합니다. `config.py`(PAGE_CONFIG)와 `logic.py`(run 함수) 두 개를 필수로 export 합니다.
- **docs/**: 프로젝트 아키텍처/디자인 문서.

## 실행 방법

```bash
# venv 활성화
source /home/daumsoft/users/hsjang/Agent_test_page/.venv/bin/activate

# 프로젝트 루트로 이동
cd /home/daumsoft/users/hsjang/Agent_test_page/mfds_test_page

# (선택) .env 에 LLM API 키 입력 — 아래 "LLM 연결" 섹션 참고

# 앱 실행
streamlit run app.py
```

## LLM 연결 (선택)

`.env` 파일을 열고 사용할 제공자의 키만 넣으면 됩니다. `.env.example` 에 템플릿이 있습니다.

```bash
# OpenAI (GPT) 만 사용
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini     # 기본값, 바꿔도 됨

# 또는 Google Gemini 만 사용
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

# 둘 다 넣으면 사이드바에서 선택 가능
```

- **아무 키도 없으면** 자동으로 "데모 Placeholder" 모드로 동작합니다(실제 LLM 호출 없이 더미 JSON 반환).
- **키가 하나라도 있으면** 사이드바에 제공자 선택 라디오가 뜨고, 선택한 제공자로 각 단계의 프롬프트가 실제 호출됩니다.
- 호출 실패 시(네트워크/키 오류 등) 해당 단계 결과에 `_error` 필드가 포함되고 파이프라인은 계속 진행합니다.
- 모델 이름은 `OPENAI_MODEL` / `GEMINI_MODEL` 환경변수로 언제든 바꿀 수 있습니다.
- `.env` 는 `.gitignore` 에 포함되어 있어 커밋되지 않습니다.

## 새 분석 페이지 추가 방법

1. **템플릿 복사**: `page_modules/_template/` 를 복사해서 `page_modules/<새_페이지_slug>/` 로 이름 변경.
2. **PRD 작성**: 복사한 폴더의 `prd.md` 를 새 분석의 목적/입력/프로세스/결과 구조에 맞게 작성.
3. **config.py 수정**: `PAGE_CONFIG` 의 `slug`, `title`, `description`, `inputs`(InputIndex 목록), `steps`(ProcessStep 목록)을 채웁니다.
4. **logic.py 구현**: `run(inputs: dict[str, str]) -> ProcessResult` 함수에 전처리 → 세분화 → 최종 → 취합 로직을 구현하고, 중간 결과는 `ProcessResult.intermediates` 에, 최종 텍스트는 `final_text` 에 담습니다.
5. **pages/ 에 wrapper 추가**: `pages/N_<표시이름>.py` 파일을 만들고 `common.page_loader` 를 통해 해당 `page_modules/<slug>` 를 로드/렌더합니다.

자세한 API 계약은 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 참고.
