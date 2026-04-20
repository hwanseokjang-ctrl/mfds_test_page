"""제품명 분석 페이지의 로직 (placeholder 데모 구현).

이 모듈은 아직 실제 LLM 에 연결되어 있지 않다. 대신 PRD 에 정의된 프롬프트
템플릿(``prompts.py``)을 실제로 ``.replace`` 로 치환해 "전송될 프롬프트"를
생성하고, 단계별로 PRD 응답 스키마에 맞는 placeholder JSON 을 반환한다.

실제 LLM 연결 시 ``_call_llm(prompt)`` 자리에 API 클라이언트를 넣으면 된다.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from common import llm_client
from common.llm_process import ProcessResult, StepEvent

from . import prompts


# 세분화 1~6 을 동시에 호출할 워커 풀 크기.
# 세분화 개수가 고정(6)이므로 동일하게 맞춤. 필요 시 조정.
_SEG_PARALLELISM = 6


def _normalize(text: str) -> str:
    """양끝 공백 제거 + 내부 다중 공백 단일화."""

    return " ".join((text or "").split())


def _call_llm(
    prompt: str,
    *,
    placeholder: Any,
    response_format: Literal["json", "text"] = "json",
    settings: dict[str, Any] | None = None,
) -> Any:
    """활성 LLM provider 를 통해 호출. 실패/미연결 시 placeholder 반환.

    ``settings`` 는 ``llm_client.snapshot_settings()`` 결과로,
    워커 스레드에서 Streamlit session_state 접근 없이 호출할 때 사용한다.
    메인 스레드라면 생략해도 된다.
    """

    kwargs = dict(settings or {})
    return llm_client.call(
        prompt,
        placeholder=placeholder,
        response_format=response_format,
        **kwargs,
    )


# -------------------------------------------------------------------------
# Placeholder 생성기: 입력에 따라 그럴듯한 형태의 더미 결과를 반환
# -------------------------------------------------------------------------

def _placeholder_preprocess(product_name: str) -> dict[str, Any]:
    """전처리 placeholder — 간단한 공백 분해 후 (F) 로 일괄 분류."""

    tokens = [t for t in product_name.split() if t] or [product_name]
    classified = [
        {
            "token": tok,
            "category": "F",
            "reason": "데모 placeholder — 실제 분류 규칙은 LLM 이 수행",
        }
        for tok in tokens
    ]
    return {"tokens": classified, "note": "placeholder 데모. 실제 (A)~(G) 분류는 LLM 연결 시 대체."}


def _format_pre_out(pre_result: Any) -> str:
    """후속 세분화 프롬프트에 삽입할 PRE_out 문자열 정리.

    - ``str`` (실제 LLM 텍스트 응답): 그대로 사용
    - ``dict`` with ``tokens`` (placeholder): 토큰 목록을 " - X → (Y) Z" 라인으로 포맷
    - 그 외: 문자열화
    """

    if isinstance(pre_result, str):
        return pre_result.strip() or "(분해 결과 없음)"
    if isinstance(pre_result, dict):
        tokens = pre_result.get("tokens", [])
        if tokens:
            return "\n".join(
                f"- {t.get('token','')} → ({t.get('category','?')}) {t.get('reason','')}"
                for t in tokens
            )
        # 파싱 실패 / 에러 케이스: raw 응답 또는 전체를 그대로
        for k in ("_raw_response", "_raw", "note"):
            if pre_result.get(k):
                return str(pre_result[k])
    return str(pre_result)


def _placeholder_seg(i: int, product_name: str, ingredients: str) -> dict[str, Any]:
    """세분화 분석 i(1..6) 의 placeholder JSON 응답.

    실제 LLM 응답을 흉내낸 더미 값으로, aggregate 단계의 패턴 1/2/3 이 모두 시연되도록
    seg_1~3 을 "해당" 으로 두고 seg_4~6 은 "해당없음" 으로 둔다.
    """

    base = f"[데모 placeholder] 세분화 {i} 규칙 기준 판정."
    if i == 1:
        return {
            "result": "해당",
            "reason": base + " 원재료명/성분명 토큰이 제품명에 포함됨.",
            "keyword_list": "쌀, 보리",
            "err_keyword_list": "",
            "passed_list": "쌀, 보리",
        }
    if i == 2:
        return {
            "result": "해당",
            "reason": base + " 통칭명(C) 토큰 존재.",
            "keyword_list": "쌀, 보리, 현미, 기장",
            "err_keyword_list": "기장",
            "passed_list": "쌀, 보리, 현미",
        }
    if i == 3:
        return {
            "result": "해당",
            "reason": base + " 식품유형명(미숫가루) 포함.",
            "keyword_list": "미숫가루",
            "err_keyword_list": "",
            "passed_list": "미숫가루",
        }
    if i == 4:
        return {
            "result": "해당없음",
            "reason": base + " 추출물/농축액 형태 원재료 없음.",
            "keyword_list": "",
            "err_keyword_list": "",
            "passed_list": "",
        }
    if i == 5:
        return {
            "result": "해당없음",
            "reason": base + " 요리명 안내 대상 아님.",
            "keyword_list": "",
            "err_keyword_list": "",
            "passed_list": "",
        }
    # i == 6
    return {
        "result": "해당없음",
        "reason": base + " 맛/향(E) 토큰 없음.",
        "keyword_list": "",
        "err_keyword_list": "",
        "passed_list": "",
    }


# -------------------------------------------------------------------------
# 취합: Python 패턴 로직 (PRD: "LLM 이 아닌 Python 구현")
#
# aggregate 최종 텍스트는 1~4번 섹션으로 구성한다. (4번은 규칙 미정 → 생략)
#   1번: 개요 — 제품명에 포함된 함량 표시 대상 명칭 요약
#   2번: 법률 정보 — 각 세분화별 법률 패턴 (세분화 1~6 각각에 대응)
#   3번: 원재료 확인 — 준수/미준수 원재료 실제 매칭 결과
#   4번: (미정 — 규칙 확정 후 추가)
# -------------------------------------------------------------------------

# 세분화 1~6 각각에 대응하는 법률 패턴.
# 자리표시자: {제품명}, {key_list}  (key_list 는 이미 ', '.join(["'X'",...]) 형태)
_LAW_PATTERNS: list[str] = [
    # seg_1 — 원재료명
    "제품명 '{제품명}'에 원재료명에 해당하는 {key_list} 명칭이 포함되었으므로 {key_list}의 명칭과 함량(백분율, 중량, 용량)을 주표시면에 14포인트 이상의 글씨로 표시하여야 한다. 다만, 제품명의 글씨크기가 22포인트 미만인 경우에는 7포인트 이상의 글씨로 표시할 수 있다.",
    # seg_2 — 통칭명(C)
    "제품명 '{제품명}'에 통칭명에 해당하는 {key_list} 명칭이 포함되었으므로 {key_list}의 명칭과 함량을 주표시면에 14포인트 이상의 글씨로 표시하여야 한다. 다만, 제품명의 글씨크기가 22포인트 미만인 경우에는 7포인트 이상의 글씨로 표시할 수 있다.",
    # seg_3 — 식품유형명/편의식품류명/요리명(D)
    "제품명 '{제품명}'에 식품유형명, 즉석섭취ㆍ편의식품류명 또는 요리명에 해당하는 {key_list} 명칭이 포함되었으며, 이 경우 함량표시를 하지 않을 수 있다. 단,「요리명을 제품명으로 사용한 경우, 제품명에 원재료명 또는 원재료명의 일부를 사용한 것으로 볼 것인지 요리명으로 볼 것인지에 따라 표시방법이 달라지는데, 그 구분이 명확하지 않으므로 유권해석 등을 받는 것을 권장」",
    # seg_4 — 추출물/농축액
    "제품명 '{제품명}'에 추출물/농축액에 해당하는 {key_list} 명칭이 포함되었으므로 {key_list}의 명칭과 함량을 주표시면에 14포인트 이상의 글씨로 표시하여야 한다. 다만, 제품명의 글씨크기가 22포인트 미만인 경우에는 7포인트 이상의 글씨로 표시할 수 있다. 식품의 원재료로서 사용한 추출물(또는 농축액)의 함량을 표시하는 때에는 추출물(또는 농축액)의 함량과 그 추출물(또는 농축액)중에 함유된 고형분 함량(백분율)을 함께 표시하여야 한다. 다만, 고형분 함량의 측정이 어려운 경우 배합함량으로 표시할 수 있다.",
    # seg_5 — 성분명 안내
    "제품명 '{제품명}'에 성분명에 해당하는 {key_list} 명칭이 포함되었으므로 {key_list}의 명칭과 함량을 주표시면에 14포인트 이상의 글씨로 표시하여야 한다. 다만, 제품명의 글씨크기가 22포인트 미만인 경우에는 7포인트 이상의 글씨로 표시할 수 있다.",
    # seg_6 — 맛/향(E)
    "제품명 '{제품명}'에 맛/향에 해당하는 {key_list} 명칭이 포함되었으므로 {key_list}의 글씨크기는 제품명과 같거나 크게 표시하고, 제품명 주위에 '합성OO향 첨가(함유)' 또는 '합성향료 첨가(함유)' 등의 표시를 하여야 한다. 다만, 해당 원재료의 '맛' 또는 '향'을 내기 위해 향료물질로 사용한 것이 합성향료물질로만 구성된 것에 한한다."
]


def _split_list(value: Any) -> list[str]:
    """``keyword_list`` / ``err_keyword_list`` / ``passed_list`` 값을 키워드 리스트로 정리.

    LLM 응답은 보통 ``"쌀, 보리"`` 형태의 쉼표 구분 문자열이지만,
    간혹 리스트로 올 수도 있어 양쪽 모두 처리한다.
    """

    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    return []


def _dedupe_ordered(items: list[str]) -> list[str]:
    """삽입 순서를 보존하며 중복 제거."""

    return list(dict.fromkeys(items))


def _format_keys(items: list[str]) -> str:
    """PRD 규칙의 ``', '.join(["'" + v + "'" for v in ...])`` 포맷."""

    return ", ".join(f"'{v}'" for v in items)


def _span(text: str, color: str, bold: bool = True) -> str:
    """인라인 HTML color span 래퍼."""
    weight = "font-weight:bold;" if bold else ""
    return f'<span style="color:{color};{weight}">{text}</span>'


def _format_keys_md(items: list[str], color: str = "#0d6efd") -> str:
    """키워드 목록을 색상 bold span으로 포맷."""
    return ", ".join(_span(f"'{v}'", color) for v in items)


def _josa_eun_neun(word: str) -> str:
    """마지막 글자의 받침 유무에 따라 '은' 또는 '는' 반환."""
    if not word:
        return "은"
    last = word[-1]
    code = ord(last)
    if 0xAC00 <= code <= 0xD7A3:
        return "은" if (code - 0xAC00) % 28 != 0 else "는"
    return "은"


# 세분화 인덱스(0~5)별 명칭 유형 레이블
_SEG_TYPE_LABELS: list[str] = [
    "원재료 명칭",                                                         # seg_1
    "통칭명",                                                              # seg_2
    "식품유형명/즉석섭취·편의식품류명/요리명",                               # seg_3
    "추출물/농축액 명칭",                                                   # seg_4
    "성분명",                                                              # seg_5
    '"맛" 또는 "향"을 내기 위하여 사용한 향료의(합성향료) 명칭',              # seg_6
]


def _parse_ingredients(ingredients: str) -> list[str]:
    """원재료 입력 필드를 최상위 쉼표 기준으로 분해.

    괄호 안의 쉼표(예: ``"밀가루(밀:미국산, 호주산)"``)는 분리하지 않는다.
    """

    tokens: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in ingredients or "":
        if ch in "([{":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == "," and depth == 0:
            tok = "".join(buf).strip()
            if tok:
                tokens.append(tok)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        tokens.append(tail)
    return tokens


_PCT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")


def _canonical_ingredient(token: str) -> str:
    """원재료 토큰에서 괄호 블록과 함량(%) 표기를 제거한 '핵심 이름'."""

    core = re.sub(r"\([^)]*\)", "", token)
    core = _PCT_RE.sub("", core)
    return " ".join(core.split()).strip()


def _match_real(keywords: list[str], ingredient_tokens: list[str]) -> list[str]:
    """``keywords`` 중 실제 원재료 토큰과 매칭되는 '핵심 이름'을 반환.

    PRD 규칙에 따라 부분 매칭을 허용한다(예: 키워드 "자몽" → "레드자몽농축액").
    반환값은 실제 원재료 측의 canonical 이름(괄호/%% 제거)이며, 순서는 키워드
    등장 순서를 보존한다.
    """

    matched: list[str] = []
    seen: set[str] = set()
    canon_tokens = [(t, _canonical_ingredient(t)) for t in ingredient_tokens]
    for kw in keywords:
        kw_canon = _canonical_ingredient(kw)
        if not kw_canon:
            continue
        for _orig, tok_canon in canon_tokens:
            if not tok_canon:
                continue
            if kw_canon in tok_canon or tok_canon in kw_canon:
                if tok_canon not in seen:
                    seen.add(tok_canon)
                    matched.append(tok_canon)
    return matched


def _build_text_1(product_name: str, seg_results: list[dict[str, Any]]) -> str:
    """1번: 제품명 구성에 따른 주표시면 함량 표시 대상 여부 확인."""
    seg_keys: list[list[str]] = [
        _dedupe_ordered(_split_list(r.get("keyword_list")))
        if r.get("result") == "해당" else []
        for r in seg_results
    ]

    # seg_4(index 3)가 seg_1(index 0)에 우선 — 같은 키워드는 seg_4로만 표시
    seg4_set = set(seg_keys[3])
    seg_keys[0] = [k for k in seg_keys[0] if k not in seg4_set]

    pname_span = _span(product_name, "#170678")
    lines: list[str] = []

    # 주표시면 함량 표시 대상 명칭 (seg_1, seg_2, seg_4, seg_5, seg_6)
    for idx in [0, 1, 3, 4, 5]:
        for kw in seg_keys[idx]:
            kw_span = _format_keys_md([kw])
            label = _SEG_TYPE_LABELS[idx]
            particle = _josa_eun_neun(kw)
            lines.append(
                f'제품명 "{pname_span}"에 포함된 {kw_span}{particle} {label}으로 주표시면 함량 표시 대상입니다.'
            )

    # 주표시면 함량 표시 대상이 아닌 명칭 (seg_3)
    for kw in seg_keys[2]:
        kw_span = _format_keys_md([kw])
        label = _SEG_TYPE_LABELS[2]
        particle = _josa_eun_neun(kw)
        lines.append(
            f'제품명 "{pname_span}"에 포함된 {kw_span}{particle} {label}으로 주표시면 함량 표시 대상이 아닙니다.'
        )

    if not lines:
        return f"제품명 '{pname_span}'에는 주표시면 함량 표시 대상 명칭이 포함되어 있지 않습니다."
    return "\n".join(f"- {line}" for line in lines)


def _build_text_2(seg_results: list[dict[str, Any]]) -> str:
    """2번: 원재료명 필드 확인 — 세분화별 분리 분석 (seg_3 제외, seg_4 우선)."""
    _FIELD_LABELS: list[str | None] = [
        "원재료 명칭",
        "통칭명",
        None,  # seg_3 제외
        "추출물/농축액 명칭",
        "성분명",
        '"맛" 또는 "향"을 내기 위하여 사용한 향료의(합성향료) 명칭',
    ]

    seg4_set: set[str] = (
        set(_split_list(seg_results[3].get("keyword_list")))
        if len(seg_results) > 3 and seg_results[3].get("result") == "해당"
        else set()
    )

    lines: list[str] = []
    for idx in [0, 3, 1, 4, 5]:
        r = seg_results[idx] if idx < len(seg_results) else {}
        if r.get("result") != "해당":
            continue

        type_label = _FIELD_LABELS[idx]
        all_keys = _dedupe_ordered(_split_list(r.get("keyword_list")))
        err_keys = _dedupe_ordered(_split_list(r.get("err_keyword_list")))
        passed_keys = _dedupe_ordered(_split_list(r.get("passed_list")))

        # seg_4 우선: seg_1에서 seg_4와 겹치는 키워드 제거
        if idx == 0:
            all_keys = [k for k in all_keys if k not in seg4_set]
            err_keys = [k for k in err_keys if k not in seg4_set]
            if not all_keys and not err_keys:
                continue

        pass_keys = [k for k in all_keys if k not in set(err_keys)]

        if pass_keys:
            pass_colored = _format_keys_md(pass_keys, '#198754')
            passed_colored = _format_keys_md(passed_keys, '#198754')
            particle = _josa_eun_neun(pass_keys[-1])
            if err_keys:
                err_colored = _format_keys_md(err_keys, '#dc3545')
                err_particle = _josa_eun_neun(err_keys[-1])
                lines.append(
                    f"{type_label}인 {pass_colored}{particle} 원재료명 필드에 "
                    f"{passed_colored}의 형식으로 표시되어 있지만, "
                    f"{err_colored}{err_particle} 포함되어 있지 않습니다."
                )
            else:
                lines.append(
                    f"{type_label}인 {pass_colored}{particle} 원재료명 필드에 "
                    f"{passed_colored}의 형식으로 표시되어 있습니다."
                )
        elif err_keys:
            err_colored = _format_keys_md(err_keys, '#dc3545')
            err_particle = _josa_eun_neun(err_keys[-1])
            lines.append(
                f"{type_label}인 {err_colored}{err_particle} 원재료명 필드에 포함되어 있지 않습니다."
            )

    if not lines:
        return "해당 제품명에는 원재료명 필드에서 확인해야 하는 명칭이 없습니다."
    return "\n".join(f"- {line}" for line in lines)


def _build_text_3(product_name: str, seg_results: list[dict[str, Any]]) -> str:
    """3번: 답변 분류 유형에 따른 주표시면 함량 표시 기준 안내 (모든 세분화 포함).

    seg_4(추출물/농축액)가 seg_1(원재료명)에 우선 — 같은 키워드는 seg_4 법률만 표시.
    """
    seg4_set: set[str] = (
        set(_split_list(seg_results[3].get("keyword_list")))
        if len(seg_results) > 3 and seg_results[3].get("result") == "해당"
        else set()
    )

    if not any(r.get("result") == "해당" for r in seg_results):
        return "해당 제품명에는 규정에 의해 표시해야 하는 명칭이 없습니다."

    pname_colored = _span(product_name, "#170678")
    lines: list[str] = []
    for idx in [0, 3, 1, 4, 5, 2]:
        r = seg_results[idx] if idx < len(seg_results) else {}
        if r.get("result") != "해당":
            continue
        keys = _dedupe_ordered(_split_list(r.get("keyword_list")))

        # seg_4 우선: seg_1에서 seg_4와 겹치는 키워드 제거
        if idx == 0:
            keys = [k for k in keys if k not in seg4_set]
            if not keys:
                continue

        key_list = _format_keys_md(keys)
        pattern = _LAW_PATTERNS[idx].format(제품명=pname_colored, key_list=key_list)
        lines.append(f"- {pattern}")
    return "\n\n".join(lines)


def _aggregate(
    product_name: str,
    ingredients: str,
    seg_results: list[dict[str, Any]],
) -> str:
    """6종 JSON 결과를 패턴 단위로 취합해 최종 마크다운+HTML 텍스트 생성."""

    normalized: list[dict[str, Any]] = [
        r if isinstance(r, dict) else {"result": "해당없음"} for r in seg_results
    ]

    # 최종 판정: seg_3(식품유형명/요리명)은 면제 대상이므로 제외하고 판정
    applicable_any = any(
        r.get("result") == "해당" for i, r in enumerate(normalized) if i != 2
    )
    if applicable_any:
        judgment_html = _span("⚠️ 주표시면 함량 표시 해당", "#dc3545")
    else:
        judgment_html = _span("✅ 주표시면 함량 표시 해당없음", "#198754")

    text_1 = _build_text_1(product_name, normalized)
    text_2 = _build_text_2(normalized)
    text_3 = _build_text_3(product_name, normalized)

    lines: list[str] = [
        f"## 📋 분석 결과 — **'{product_name}'**",
        "",
        f"> **최종 판정:** {judgment_html}",
        "",
        "---",
        "### 1. 제품명 구성에 따른 주표시면 함량 표시 대상 여부 확인",
        text_1,
        "",
        "---",
        "### 2. 원재료명 필드 확인",
        text_2,
        "",
        "---",
        "### 3. 답변 분류 유형에 따른 주표시면 함량 표시 기준 안내",
        text_3,
    ]
    return "\n".join(lines)


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def run_steps(inputs: dict[str, str]) -> Iterator[StepEvent]:
    """단계별 이벤트를 yield 하는 파이프라인 러너.

    흐름:
        1. 전처리 (LLM 1회, 직렬) — PRE_out 생성
        2. 세분화 1~6 (LLM 6회, **병렬**) — 모두 PRE_out 을 입력으로 받음
        3. 취합 (Python, 직렬)

    세분화는 서로 독립이라 동시 실행이 안전하다. 메인 스레드에서 LLM 설정을
    스냅샷 해 워커에 전달하므로, 실행 도중 사용자가 제공자/모델을 바꿔도 이번
    실행에는 영향이 없다.
    """

    product_name = _normalize(inputs.get("product_name", ""))
    ingredients = _normalize(inputs.get("ingredients", ""))

    # LLM 설정 스냅샷 (워커 스레드는 session_state 접근 불가하므로 여기서 떠 둔다).
    settings = llm_client.snapshot_settings()
    provider_info: llm_client.ProviderInfo = settings["provider"]
    if provider_info.name == "placeholder":
        provider_note = "데모 placeholder"
    else:
        provider_note = (
            f"{provider_info.display} · `{settings['model']}` · effort={settings['effort']}"
        )

    # 1) 전처리 — 직렬
    # 프롬프트는 prompts.get_template(key) 로 조회 (세션 편집값이 있으면 우선).
    pre_prompt = prompts.render(
        prompts.get_template("preprocess"),
        제품명=product_name,
        원재료명=ingredients,
    )
    pre_result = _call_llm(
        pre_prompt,
        placeholder=_placeholder_preprocess(product_name),
        response_format="text",
        settings=settings,
    )
    yield StepEvent(
        step_key="preprocess",
        prompt=pre_prompt,
        result=pre_result,
        note=f"LLM 호출({provider_note}): 제품명 토큰 분해 및 (A)~(G) 분류",
    )

    pre_out_str = _format_pre_out(pre_result)

    # 2) 세분화 6종 — 병렬 실행
    # 각 세분화 프롬프트도 get_template("seg_N") 으로 조회 (세션 편집값 반영).
    seg_specs: list[tuple[int, str, dict[str, Any]]] = []
    for i in range(1, 7):
        template = prompts.get_template(f"seg_{i}")
        seg_prompt = prompts.render(
            template,
            제품명=product_name,
            원재료명=ingredients,
            PRE_out=pre_out_str,
        )
        placeholder = _placeholder_seg(i, product_name, ingredients)
        seg_specs.append((i, seg_prompt, placeholder))

    seg_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=_SEG_PARALLELISM, thread_name_prefix="seg") as pool:
        # 모든 세분화를 즉시 제출 (여기서 wall-time 이 시작됨).
        futures = {
            i: pool.submit(
                _call_llm,
                prompt,
                placeholder=placeholder,
                response_format="json",
                settings=settings,
            )
            for i, prompt, placeholder in seg_specs
        }

        # seg_1 → seg_6 순서로 결과를 기다려 UI 표시 순서를 유지.
        # (병렬 호출된 futures 들이 이미 완료되어 있으면 .result() 는 즉시 반환)
        for i, seg_prompt, _placeholder in seg_specs:
            seg_result = futures[i].result()
            seg_results.append(
                seg_result if isinstance(seg_result, dict) else {"result": "해당없음", "_raw": seg_result}
            )
            yield StepEvent(
                step_key=f"seg_{i}",
                prompt=seg_prompt,
                result=seg_result,
                note=f"LLM 호출({provider_note}): 세분화 분석 {i} — 6종 병렬 실행 중 {i}번째 응답",
            )

    # 3) 취합 (Python 패턴 로직) — LLM 호출 없음
    final_text = _aggregate(product_name, ingredients, seg_results)
    yield StepEvent(
        step_key="aggregate",
        prompt=None,
        result=final_text,
        note="LLM 호출 아님. Python 패턴 로직으로 6종 결과 취합.",
    )


def run(inputs: dict[str, str]) -> ProcessResult:
    """호환용 단일 호출 API. ``run_steps`` 를 돌려 ``ProcessResult`` 로 묶어 반환."""

    intermediates: dict[str, Any] = {}
    final_text = ""
    for event in run_steps(inputs):
        entry: dict[str, Any] = {"result": event.result}
        if event.prompt is not None:
            entry["prompt"] = event.prompt
        if event.note:
            entry["note"] = event.note
        intermediates[event.step_key] = entry
        if event.step_key == "aggregate" and isinstance(event.result, str):
            final_text = event.result
    return ProcessResult(intermediates=intermediates, final_text=final_text)
