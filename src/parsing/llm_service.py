"""
LLM abstraction layer for model-agnostic AI parsing.

Provides a unified interface for different LLM providers (OpenAI, Anthropic, etc.)
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import json


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"  # For testing


class LLMResponse(BaseModel):
    """Standardized LLM response"""
    content: str = Field(description="The generated text content")
    provider: LLMProvider = Field(description="The LLM provider used")
    model: str = Field(description="The specific model used")
    tokens_used: Optional[int] = Field(default=None, description="Number of tokens used")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provider-specific metadata")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate text from a prompt.
        
        Args:
            prompt: The input prompt
            **kwargs: Provider-specific parameters
            
        Returns:
            Standardized LLM response
        """
        pass


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing and development"""
    
    def __init__(self, model: str = "mock-model"):
        self.model = model
    
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Mock implementation that returns a deterministic transaction.
        
        For testing purposes, this extracts basic information from the prompt
        or returns a standard mock transaction.
        """
        # Simple mock response for transaction parsing
        mock_transaction = {
            "transaction_type": "debit",
            "amount": "25.00",
            "currency": "USD",
            "merchant": "Test Merchant",
            "description": "Test transaction",
            "confidence_score": 0.85
        }
        
        return LLMResponse(
            content=json.dumps(mock_transaction),
            provider=LLMProvider.MOCK,
            model=self.model,
            tokens_used=100,
            metadata={"mock": True}
        )


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client (GPT models)"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    def _get_client(self):
        """Lazy initialization of OpenAI client"""
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._client
    
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate text using OpenAI API.
        
        Args:
            prompt: The input prompt
            **kwargs: OpenAI-specific parameters (temperature, max_tokens, etc.)
        """
        client = self._get_client()
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.1),  # Low temperature for consistency
            max_tokens=kwargs.get("max_tokens", 500),
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            provider=LLMProvider.OPENAI,
            model=self.model,
            tokens_used=response.usage.total_tokens,
            metadata={
                "finish_reason": response.choices[0].finish_reason,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        )


class AnthropicClient(BaseLLMClient):
    """Anthropic LLM client (Claude models)"""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    def _get_client(self):
        """Lazy initialization of Anthropic client"""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._client
    
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate text using Anthropic API.
        
        Args:
            prompt: The input prompt
            **kwargs: Anthropic-specific parameters
        """
        client = self._get_client()
        
        response = client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 500),
            temperature=kwargs.get("temperature", 0.1),
            messages=[{"role": "user", "content": prompt}]
        )
        
        return LLMResponse(
            content=response.content[0].text,
            provider=LLMProvider.ANTHROPIC,
            model=self.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            metadata={
                "stop_reason": response.stop_reason,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        )


class LLMService:
    """
    Main LLM service that manages different providers.
    
    This service provides a unified interface for interacting with various
    LLM providers in a model-agnostic way.
    """
    
    def __init__(
        self,
        provider: LLMProvider = LLMProvider.MOCK,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize LLM service with specified provider.
        
        Args:
            provider: The LLM provider to use
            api_key: API key for the provider (if required)
            model: Specific model to use (provider-specific)
        """
        self.provider = provider
        self.client = self._create_client(provider, api_key, model)
    
    def _create_client(
        self,
        provider: LLMProvider,
        api_key: Optional[str],
        model: Optional[str]
    ) -> BaseLLMClient:
        """Create the appropriate LLM client based on provider"""
        if provider == LLMProvider.MOCK:
            return MockLLMClient(model=model or "mock-model")
        
        elif provider == LLMProvider.OPENAI:
            if not api_key:
                raise ValueError("API key required for OpenAI provider")
            return OpenAIClient(api_key=api_key, model=model or "gpt-4")
        
        elif provider == LLMProvider.ANTHROPIC:
            if not api_key:
                raise ValueError("API key required for Anthropic provider")
            return AnthropicClient(api_key=api_key, model=model or "claude-3-sonnet-20240229")
        
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate text using the configured LLM provider.
        
        Args:
            prompt: The input prompt
            **kwargs: Provider-specific parameters
            
        Returns:
            Standardized LLM response
        """
        return await self.client.generate(prompt, **kwargs)
