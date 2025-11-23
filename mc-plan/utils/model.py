"""LLM Wrapper 모듈

제공 Provider별(OpenAI, Google Gemini, Anthropic Claude) 공통 인터페이스를 갖는
Wrapper 클래스와 Factory 구현.

사용 예시:

from utils.model import LLMFactory

client = LLMFactory.create(
    provider="openai",
    model_name="gpt-4o-mini",
    temperature=0.2,
)
result = client.generate("간단한 한국어 요약을 만들어줘: 인공지능의 장점")
print(result.text)

messages = [
    {"role": "system", "content": "당신은 간결하게 요약하는 비서입니다."},
    {"role": "user", "content": "파이썬과 자바의 차이점을 요약해줘."}
]
result = client.generate(messages)
print(result.text)

환경 변수 기본 명칭:
- OpenAI: OPENAI_API_KEY
- Gemini: GOOGLE_API_KEY (일반적으로 Google Generative AI SDK가 기대)
- Claude(Anthropic): ANTHROPIC_API_KEY

라이브러리가 설치되지 않았거나 키가 누락된 경우 명확한 에러를 발생시킵니다.
각 provider import 는 지연(import 내부 수행)하여 설치되지 않아도 파일 자체는 로드됩니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union
import os
from dotenv import load_dotenv

__all__ = [
    "GenerationResult",
    "BaseLLMClient",
    "OpenAIClient",
    "GeminiClient",
    "ClaudeClient",
    "LLMFactory",
]

PromptType = Union[str, Sequence[Dict[str, str]]]


@dataclass
class GenerationResult:
    """LLM 호출 결과 래퍼.

    text: 주 출력 텍스트 (첫 메시지 또는 텍스트 블록 병합 결과)
    provider: 사용된 LLM Provider 이름
    model: 사용된 모델명
    raw: 원본 Response 객체(라이브러리별 형식 상이)
    finish_reason: 완료 사유(OpenAI/Anthropic 등에서 제공 시)
    usage: 토큰 사용량 정보(제공되는 경우)
    """
    text: str
    provider: str
    model: str
    raw: Any = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


class BaseLLMClient:
    """LLM Client 기본 부모 클래스.

    하위 클래스는 generate() 구현만 하면 되며, 입력은 단일 문자열 또는
    OpenAI 스타일 messages(list[{"role","content"}]) 모두 허용합니다.
    """

    def __init__(
        self,
        provider: str,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.provider = provider.lower()
        self.model_name = model_name or self._default_model()
        self.api_key = api_key or self._resolve_api_key()
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _default_model(self) -> str:
        raise NotImplementedError("하위 클래스에서 기본 모델을 정의하세요.")

    def _resolve_api_key(self) -> Optional[str]:
        """Provider별 기본 환경변수 이름을 통해 API Key 획득."""
        load_dotenv()
        env_names = {
            "openai": ["OPENAI_API_KEY"],
            "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
            "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "claude": ["ANTHROPIC_API_KEY"],
        }
        for name in env_names.get(self.provider, []):
            val = os.getenv(name)
            if val:
                return val
        return None  # 키가 꼭 필요하지 않을 수도 있으므로 None 허용

    def _ensure_api_key(self):
        if not self.api_key:
            raise RuntimeError(f"{self.provider} API 키가 설정되지 않았습니다. 환경 변수 또는 api_key 인자를 제공하세요.")

    def _normalize_messages(self, prompt: PromptType) -> List[Dict[str, str]]:
        if isinstance(prompt, str):
            return [{"role": "user", "content": prompt}]
        # 시퀀스 유효성 검증: 각 dict는 role/content 포함
        normalized: List[Dict[str, str]] = []
        for m in prompt:  # type: ignore[arg-type]
            if not isinstance(m, dict) or "role" not in m or "content" not in m:
                raise ValueError("messages 리스트는 각 항목에 'role'과 'content' 키를 가진 dict여야 합니다.")
            normalized.append({"role": str(m["role"]), "content": str(m["content"])})
        return normalized

    def generate(self, prompt: PromptType, **kwargs) -> GenerationResult:  # pragma: no cover - 인터페이스
        raise NotImplementedError

    # 편의 메소드: 단일 문자열 전용
    def generate_text(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs).text


class OpenAIClient(BaseLLMClient):
    """OpenAI ChatCompletion 기반 클라이언트."""

    def _default_model(self) -> str:
        # 최신 경량 모델 기본값(필요 시 사용자 변경 가능)
        return "gpt-5-mini"

    def _get_client(self):
        try:
            from openai import OpenAI  # 지연 import
        except ImportError as e:
            raise ImportError("openai 패키지가 설치되지 않았습니다. 'pip install openai' 로 설치하세요.") from e
        self._ensure_api_key()
        return OpenAI(api_key=self.api_key)

    def generate(self, prompt: PromptType, **kwargs) -> GenerationResult:
        messages = self._normalize_messages(prompt)
        client = self._get_client()
        params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        params.update(kwargs)

        response = client.chat.completions.create(**params)
        choice = response.choices[0]
        text = choice.message.content or ""
        finish_reason = getattr(choice, "finish_reason", None)
        usage = getattr(response, "usage", None)
        usage_dict = None
        if usage:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
        return GenerationResult(
            text=text,
            provider="openai",
            model=self.model_name,
            raw=response,
            finish_reason=finish_reason,
            usage=usage_dict,
        )


class GeminiClient(BaseLLMClient):
    """Google Gemini (Generative AI) 클라이언트."""

    def _default_model(self) -> str:
        # 빠른 모델 기본값
        return "gemini-1.5-flash"

    def _get_model(self):
        try:
            import google.generativeai as genai  # 지연 import
        except ImportError as e:
            raise ImportError("google-generativeai 패키지가 설치되지 않았습니다. 'pip install google-generativeai' 로 설치하세요.") from e
        self._ensure_api_key()
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model_name)

    def _merge_messages_to_text(self, messages: List[Dict[str, str]]) -> str:
        # Gemini는 단일 prompt 문자열 형태가 간편하므로 role 구분 표시
        return "\n\n".join(f"[{m['role']}] {m['content']}" for m in messages)

    def generate(self, prompt: PromptType, **kwargs) -> GenerationResult:
        messages = self._normalize_messages(prompt)
        model = self._get_model()
        merged = self._merge_messages_to_text(messages)
        # safety 설정 등 세부 옵션은 kwargs로 주입 가능
        response = model.generate_content(merged, **kwargs)
        # response.text 속성(최신 SDK 기준)
        text = getattr(response, "text", "")
        return GenerationResult(
            text=text,
            provider="gemini",
            model=self.model_name,
            raw=response,
            finish_reason=None,
            usage=None,  # 현재 SDK 토큰 사용량 노출 방식이 제한적
        )


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude 클라이언트."""

    def _default_model(self) -> str:
        return "claude-3-haiku-20240307"

    def _get_client(self):
        try:
            import anthropic  # 지연 import
        except ImportError as e:
            raise ImportError("anthropic 패키지가 설치되지 않았습니다. 'pip install anthropic' 로 설치하세요.") from e
        self._ensure_api_key()
        return anthropic.Anthropic(api_key=self.api_key)

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        # Anthropic messages 형식: [{"role":"user"|"assistant", "content":[{"type":"text", "text":"..."}]}]
        converted: List[Dict[str, Any]] = []
        for m in messages:
            role = m["role"].lower()
            # system 메시지는 Anthropic에서 별도로 system 프롬프트로 제공 가능. 여기서는 user prefix 사용.
            if role == "system":
                # system은 첫 user 메시지 앞에 주석 형태로 삽입
                converted.append({"role": "user", "content": [{"type": "text", "text": f"(system) {m['content']}"}]})
            else:
                converted.append({"role": role, "content": [{"type": "text", "text": m["content"]}]})
        return converted

    def generate(self, prompt: PromptType, **kwargs) -> GenerationResult:
        messages = self._normalize_messages(prompt)
        client = self._get_client()
        anthropic_messages = self._convert_messages(messages)
        max_tokens = self.max_tokens or 1024
        params = {
            "model": self.model_name,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if self.top_p is not None:
            params["top_p"] = self.top_p
        params.update(kwargs)
        response = client.messages.create(**params)
        # response.content: List[ContentBlock]; text 속성 취합
        texts: List[str] = []
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "text":
                texts.append(getattr(block, "text", ""))
        merged_text = "\n".join(t for t in texts if t)
        finish_reason = getattr(response, "stop_reason", None)
        usage_info = getattr(response, "usage", None)
        usage_dict = None
        if usage_info:
            usage_dict = {
                "input_tokens": getattr(usage_info, "input_tokens", None),
                "output_tokens": getattr(usage_info, "output_tokens", None),
            }
        return GenerationResult(
            text=merged_text,
            provider="claude",
            model=self.model_name,
            raw=response,
            finish_reason=finish_reason,
            usage=usage_dict,
        )


class LLMFactory:
    """Provider 문자열로 적절한 LLM Client 인스턴스 생성하는 Factory."""

    _PROVIDER_MAP = {
        "openai": OpenAIClient,
        "gpt": OpenAIClient,
        "gemini": GeminiClient,
        "google": GeminiClient,
        "claude": ClaudeClient,
        "anthropic": ClaudeClient,
    }

    @classmethod
    def create(cls, provider: str, **kwargs) -> BaseLLMClient:
        if not provider:
            raise ValueError("provider 문자열을 제공해야 합니다.")
        key = provider.lower()
        client_cls = cls._PROVIDER_MAP.get(key)
        if not client_cls:
            supported = ", ".join(sorted(set(cls._PROVIDER_MAP.keys())))
            raise ValueError(f"지원하지 않는 provider: {provider}. 지원 목록: {supported}")
        # provider 전달(표준화된 이름 전달 위해 key 사용)
        return client_cls(provider=key, **kwargs)


def _demo():  # pragma: no cover - 간단 실행 예시
    print("[LLMFactory Demo] 환경 변수 설정 여부에 따라 호출이 실패할 수 있습니다.")
    for prov in ["openai"]:
        try:
            client = LLMFactory.create(prov, temperature=1.0, model_name="gpt-5-nano")
            res = client.generate("저녁 메뉴 추천해줘. 한식으로!(2-3문장 이내)")
            print(f"{prov} => {res.text[:80]}...")
        except Exception as e:
            print(f"{prov} 호출 스킵(사유: {e})")


if __name__ == "__main__":  # 수동 테스트
    _demo()
