"""
LangChain Cerebras Compatibility Module - Native Implementation

Provides ChatCerebras class using cerebras-cloud-sdk directly.
NO OpenAI dependencies - pure Cerebras integration with LangChain.

Usage:
    from app.services.langchain_cerebras_compat import ChatCerebras

    llm = ChatCerebras(
        model="llama-3.3-70b",
        api_key=os.getenv("CEREBRAS_API_KEY"),
        temperature=0.7
    )
"""

import os
from typing import Any, Iterator, List, Optional, Union

from cerebras.cloud.sdk import Cerebras
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult


class ChatCerebras(BaseChatModel):
    """
    Native ChatCerebras using cerebras-cloud-sdk.

    Direct integration with Cerebras API - NO OpenAI dependencies.

    Available models (Dec 2025):
    - llama-3.3-70b: Ultra-fast ($0.10/M tokens), 1800 tok/s
    - llama-3.3-70b: Latest Llama 3.3 ($0.60/M tokens), 450 tok/s
    - qwen-3-32b: Multi-lingual, excellent for code
    - qwen-3-235b-a22b-instruct-2507: Large MoE, complex reasoning
    - gpt-oss-120b: Large open-source model
    - zai-glm-4.6: Chinese/multi-lingual specialized

    Performance:
    - 20x faster than GPU-based cloud inference
    - 240ms time-to-first-token on 405B models
    - Full 16-bit precision (no accuracy loss)
    """

    model: str = "llama-3.3-70b"
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    _client: Optional[Cerebras] = None

    def __init__(
        self,
        model: str = "llama-3.3-70b",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ):
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("CEREBRAS_API_KEY")

        if not api_key:
            raise ValueError(
                "Cerebras API key not found. Set CEREBRAS_API_KEY environment variable "
                "or pass api_key parameter."
            )

        super().__init__(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        # Initialize Cerebras client
        self._client = Cerebras(api_key=api_key)

    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM."""
        return "cerebras"

    def _convert_message_to_dict(self, message: BaseMessage) -> dict:
        """Convert a LangChain message to Cerebras API format."""
        if isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        elif isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            return {"role": "assistant", "content": message.content}
        else:
            return {"role": "user", "content": str(message.content)}

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a chat completion using Cerebras API."""
        # Convert messages to Cerebras format
        cerebras_messages = [
            self._convert_message_to_dict(msg) for msg in messages
        ]

        # Build request parameters
        request_params = {
            "model": self.model,
            "messages": cerebras_messages,
            "temperature": self.temperature,
        }

        if self.max_tokens:
            request_params["max_tokens"] = self.max_tokens

        if stop:
            request_params["stop"] = stop

        # Call Cerebras API
        response = self._client.chat.completions.create(**request_params)

        # Extract the response content
        content = response.choices[0].message.content

        # Create ChatResult
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    @property
    def _identifying_params(self) -> dict:
        """Return identifying parameters."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
