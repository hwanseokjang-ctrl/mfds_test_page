"""LLM 제공자(OpenAI / Google Gemini) 통합 클라이언트.

- ``.env`` 에 설정된 API 키에 따라 사용 가능한 provider 를 자동 탐지한다.
- 사용자는 페이지 내 LLM 패널에서 provider/model/temperature 를 선택할 수 있고,
  선택값은 Streamlit session state 에 저장되어 페이지 간 공유된다.
- 키가 없거나 호출이 실패하면 ``placeholder`` 로 안전하게 폴백한다.
- 모델 카탈로그(``MODEL_CATALOG``)는 참고 프로젝트의 ``MODEL_OPTIONS`` 패턴을
  Streamlit 에 맞게 단순화한 것으로, 각 모델의 ``reasoning_style`` 에 따라
  UI 에서 노출되는 파라미터(temperature 등)가 달라진다.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# 환경변수 로드 (import 시 1회)
# ---------------------------------------------------------------------------
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)


ProviderName = Literal["openai", "gemini", "placeholder"]
ResponseFormat = Literal["json", "text"]
ReasoningStyle = Literal["none", "effort", "thinking"]
ReasoningEffort = Literal["none", "low", "medium", "high"]

# Session state 키 — 페이지 간 공유 유지
SESSION_PROVIDER = "llm_provider_name"
SESSION_MODEL = "llm_model_name"
SESSION_TEMPERATURE = "llm_temperature"
SESSION_TOP_P = "llm_top_p"
SESSION_REASONING_EFFORT = "llm_reasoning_effort"

_PLACEHOLDER_DELAY_S = 0.45

# Gemini thinking_budget 으로 변환하는 맵핑 (토큰 단위).
# 0 = 추론 비활성, 양수 = 해당 토큰까지 thinking 허용.
_GEMINI_THINKING_BUDGET: dict[ReasoningEffort, int] = {
    "none": 0,
    "low": 2048,
    "medium": 8192,
    "high": 24576,
}


@dataclass(frozen=True)
class ModelSpec:
    """카탈로그의 한 모델 엔트리."""

    value: str
    label: str
    reasoning_style: ReasoningStyle = "none"


# ---------------------------------------------------------------------------
# 모델 카탈로그 (참고 프로젝트 MODEL_OPTIONS 패턴의 단순화 버전)
# 실제 사용 가능 모델이 바뀌면 여기만 고치면 UI/호출 전체에 반영된다.
# ---------------------------------------------------------------------------
MODEL_CATALOG: dict[ProviderName, list[ModelSpec]] = {
    "openai": [
        ModelSpec("gpt-4o", "gpt-4o (일반 · temperature/top_p)", "none"),
        ModelSpec("gpt-5.1", "gpt-5.1 (추론 · 기본)", "effort"),
        ModelSpec("gpt-5.2", "gpt-5.2 (추론 · 고품질)", "effort"),
    ],
    "gemini": [
        ModelSpec("gemini-2.5-flash", "gemini-2.5-flash (추론 · 빠름)", "thinking"),
        ModelSpec("gemini-2.5-pro", "gemini-2.5-pro (추론 · 고품질)", "thinking"),
    ],
    "placeholder": [
        ModelSpec("-", "placeholder (LLM 호출 없음)", "none"),
    ],
}


@dataclass(frozen=True)
class ProviderInfo:
    name: ProviderName
    display: str
    default_model: str
    available: bool
    hint: str = ""


def _env_model(env_name: str, fallback: str) -> str:
    return (os.environ.get(env_name) or "").strip() or fallback


def _has_key(*names: str) -> bool:
    return any((os.environ.get(n) or "").strip() for n in names)


def list_providers() -> list[ProviderInfo]:
    """사용 가능한 모든 provider 를 선순위대로 반환."""

    has_openai = _has_key("OPENAI_API_KEY")
    has_gemini = _has_key("GOOGLE_API_KEY", "GEMINI_API_KEY")
    return [
        ProviderInfo(
            name="openai",
            display="GPT (OpenAI)",
            default_model=_env_model("OPENAI_MODEL", "gpt-5.1"),
            available=has_openai,
            hint="" if has_openai else "`.env` 에 OPENAI_API_KEY 를 넣으면 활성화됩니다.",
        ),
        ProviderInfo(
            name="gemini",
            display="Gemini (Google)",
            default_model=_env_model("GEMINI_MODEL", "gemini-2.5-flash"),
            available=has_gemini,
            hint="" if has_gemini else "`.env` 에 GOOGLE_API_KEY 를 넣으면 활성화됩니다.",
        ),
        ProviderInfo(
            name="placeholder",
            display="데모 Placeholder",
            default_model="-",
            available=True,
            hint="실제 LLM 을 호출하지 않고 데모용 더미 결과를 반환합니다.",
        ),
    ]


def get_provider(name: ProviderName) -> ProviderInfo:
    for p in list_providers():
        if p.name == name:
            return p
    return list_providers()[-1]


def list_models(provider: ProviderName) -> list[ModelSpec]:
    return list(MODEL_CATALOG.get(provider, []))


def get_model_spec(provider: ProviderName, model_value: str) -> ModelSpec:
    for m in MODEL_CATALOG.get(provider, []):
        if m.value == model_value:
            return m
    models = MODEL_CATALOG.get(provider, [])
    return models[0] if models else ModelSpec("-", "-", "none")


# ---------------------------------------------------------------------------
# Session state 안전 접근
# ---------------------------------------------------------------------------

def _session_get(key: str, default: Any = None) -> Any:
    try:
        import streamlit as st

        return st.session_state.get(key, default)
    except Exception:
        return default


def get_active_provider() -> ProviderInfo:
    providers = list_providers()
    selected = _session_get(SESSION_PROVIDER)
    if selected:
        for p in providers:
            if p.name == selected and p.available:
                return p
    for p in providers:
        if p.name != "placeholder" and p.available:
            return p
    return providers[-1]


def get_active_model(provider: ProviderInfo | None = None) -> str:
    """현재 활성 모델명.

    우선순위: session_state > env(default_model) > catalog 기본값(첫 항목)
    """

    provider = provider or get_active_provider()
    catalog = list_models(provider.name)

    stored = _session_get(SESSION_MODEL)
    if stored and any(m.value == stored for m in catalog):
        return stored

    if provider.default_model and any(m.value == provider.default_model for m in catalog):
        return provider.default_model

    return catalog[0].value if catalog else "-"


def get_active_temperature() -> float:
    val = _session_get(SESSION_TEMPERATURE, 0.2)
    try:
        return max(0.0, min(2.0, float(val)))
    except (TypeError, ValueError):
        return 0.2


def get_active_top_p() -> float:
    val = _session_get(SESSION_TOP_P, 1.0)
    try:
        return max(0.0, min(1.0, float(val)))
    except (TypeError, ValueError):
        return 1.0


def get_active_reasoning_effort() -> ReasoningEffort:
    val = _session_get(SESSION_REASONING_EFFORT, "none")
    if val in ("none", "low", "medium", "high"):
        return val  # type: ignore[return-value]
    return "none"


# ---------------------------------------------------------------------------
# 실제 호출
# ---------------------------------------------------------------------------

def call(
    prompt: str,
    *,
    placeholder: Any,
    response_format: ResponseFormat = "json",
    provider: ProviderInfo | None = None,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> Any:
    """활성 provider/모델로 LLM 호출. 실패/미연결 시 placeholder 반환.

    병렬 호출 시 ``st.session_state`` 접근이 불가능한 워커 스레드를 위해
    ``provider`` / ``model`` / ``effort`` / ``temperature`` 를 **명시 인자**로
    넘길 수 있다. 메인 스레드에서 ``snapshot_settings()`` 로 현재 설정을
    한 번에 떠서 워커에 그대로 전달하는 패턴을 권장한다.
    """

    if provider is None:
        provider = get_active_provider()
    if provider.name == "placeholder":
        time.sleep(_PLACEHOLDER_DELAY_S)
        return placeholder

    if model is None:
        model = get_active_model(provider)
    if effort is None:
        effort = get_active_reasoning_effort()
    if temperature is None:
        temperature = get_active_temperature()
    if top_p is None:
        top_p = get_active_top_p()
    spec = get_model_spec(provider.name, model)

    try:
        if provider.name == "openai":
            return _call_openai(prompt, model, spec, temperature, top_p, effort, response_format, placeholder)
        if provider.name == "gemini":
            return _call_gemini(prompt, model, spec, temperature, effort, response_format, placeholder)
    except Exception as exc:  # noqa: BLE001 - 데모 환경에서 진행을 위해 폴백
        return _wrap_error(placeholder, provider, exc)

    return placeholder


def snapshot_settings() -> dict[str, Any]:
    """메인 스레드에서 현재 LLM 설정을 스냅샷으로 추출.

    반환된 dict 는 ``call(**snapshot, ...)`` 형태로 바로 넘길 수 있다.
    워커 스레드 내부에서 session_state 를 읽지 못하는 상황(parallel 호출)에
    사용한다.
    """

    provider = get_active_provider()
    return {
        "provider": provider,
        "model": get_active_model(provider),
        "effort": get_active_reasoning_effort(),
        "temperature": get_active_temperature(),
        "top_p": get_active_top_p(),
    }


def _call_openai(
    prompt: str,
    model: str,
    spec: ModelSpec,
    temperature: float,
    top_p: float,
    effort: ReasoningEffort,
    response_format: ResponseFormat,
    placeholder: Any,
) -> Any:
    from openai import OpenAI

    client = OpenAI()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if spec.reasoning_style == "effort":
        # 추론 모델: reasoning_effort 파라미터로 조절 (none 이면 파라미터 미포함).
        if effort != "none":
            kwargs["reasoning_effort"] = effort
    else:
        # 비추론 모델 (gpt-4o 등): temperature 와 top_p 전달.
        kwargs["temperature"] = temperature
        kwargs["top_p"] = top_p

    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    text = (resp.choices[0].message.content or "").strip()
    return _post_process(text, response_format, placeholder)


def _call_gemini(
    prompt: str,
    model: str,
    spec: ModelSpec,
    temperature: float,
    effort: ReasoningEffort,
    response_format: ResponseFormat,
    placeholder: Any,
) -> Any:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    config_kwargs: dict[str, Any] = {}
    if spec.reasoning_style == "thinking":
        # 추론 모델: effort → thinking_budget 토큰으로 변환.
        budget = _GEMINI_THINKING_BUDGET.get(effort, _GEMINI_THINKING_BUDGET["medium"])
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)
    else:
        # 비추론 모델: temperature 전달.
        config_kwargs["temperature"] = temperature

    if response_format == "json":
        config_kwargs["response_mime_type"] = "application/json"

    config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    resp = client.models.generate_content(model=model, contents=prompt, config=config)
    text = (getattr(resp, "text", None) or "").strip()
    return _post_process(text, response_format, placeholder)


# ---------------------------------------------------------------------------
# 후처리
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", re.DOTALL)


def _post_process(raw_text: str, response_format: ResponseFormat, placeholder: Any) -> Any:
    if not raw_text:
        return placeholder
    if response_format == "text":
        return raw_text

    candidate = raw_text
    match = _JSON_FENCE_RE.search(raw_text)
    if match:
        candidate = match.group(1)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        if isinstance(placeholder, dict):
            return {**placeholder, "_raw_response": raw_text[:1000], "_parse_error": True}
        return {"_raw_response": raw_text[:1000], "_parse_error": True}


def _wrap_error(placeholder: Any, provider: ProviderInfo, exc: Exception) -> Any:
    msg = f"{provider.display} 호출 실패: {type(exc).__name__}: {exc}"
    if isinstance(placeholder, dict):
        return {**placeholder, "_error": msg}
    return {"_error": msg, "_placeholder": placeholder}
