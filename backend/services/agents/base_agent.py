"""
Base agent class with shared LLM client and structured output handling.
"""
import os
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel


class BaseAgent:
    """
    Base class for all agents in the multi-agent system.
    
    Provides:
    - Shared OpenAI GPT-5 client
    - Structured JSON output parsing
    - Retry logic for failed API calls
    - Common prompt building utilities
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5",
        max_retries: int = 3
    ):
        """
        Initialize the base agent.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
            model: OpenAI model to use (default: gpt-5)
            max_retries: Maximum retry attempts for failed calls
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = model
        self.max_retries = max_retries
    
    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 1.0,
        max_completion_tokens: int = 4096,
        json_mode: bool = True
    ) -> str:
        """
        Call the LLM with the given prompts.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User query/task
            temperature: Ignored for GPT-5 (only default of 1 is supported)
            max_completion_tokens: Maximum tokens in response (GPT-5 parameter)
            json_mode: If True, request JSON output (via response_format)
            
        Returns:
            Raw response text
        """
        for attempt in range(self.max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    # Note: GPT-5 only supports temperature=1 (the default).
                    # Do NOT pass temperature to the API — any other value causes a 400 error.
                    "max_completion_tokens": max_completion_tokens
                }
                
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = await self.client.chat.completions.create(**kwargs)
                
                choice = response.choices[0]
                content = choice.message.content
                
                # GPT-5 can return None content (e.g. refusal, empty output)
                if not content:
                    refusal = getattr(choice.message, 'refusal', None)
                    raise RuntimeError(
                        f"GPT-5 returned empty content. "
                        f"finish_reason={choice.finish_reason}, "
                        f"refusal={refusal}"
                    )
                
                return content
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        f"Failed to call LLM after {self.max_retries} attempts: {str(e)}"
                    )
                print(f"  Retry {attempt + 1}/{self.max_retries}: {e}")
                continue
    
    async def call_with_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 1.0,
        max_completion_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Call the LLM and parse JSON response.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User query/task
            temperature: Ignored for GPT-5 (only default of 1 is supported)
            max_completion_tokens: Maximum tokens in response (GPT-5 parameter)
            
        Returns:
            Parsed JSON dict
        """
        # Add JSON instruction to user prompt
        json_instruction = "\n\nIMPORTANT: Return ONLY valid JSON, no other text."
        full_user_prompt = user_prompt + json_instruction
        
        response_text = await self.call(
            system_prompt=system_prompt,
            user_prompt=full_user_prompt,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens
        )
        
        # Parse JSON response
        try:
            # Try to extract JSON if there's extra text
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # Extract from code block
                lines = response_text.split("```")
                for line in lines:
                    if line.strip().startswith("{") or line.strip().startswith("["):
                        response_text = line.strip()
                        break
            
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse JSON response: {str(e)}\n"
                f"Response was: {response_text[:500]}..."
            )
    
    async def call_with_pydantic(
        self,
        system_prompt: str,
        user_prompt: str,
        model_class: type[BaseModel],
        temperature: float = 1.0,
        max_completion_tokens: int = 4096
    ) -> BaseModel:
        """
        Call the LLM and parse response into a Pydantic model.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User query/task
            model_class: Pydantic model class to parse into
            temperature: Ignored for GPT-5 (only default of 1 is supported)
            max_completion_tokens: Maximum tokens in response (GPT-5 parameter)
            
        Returns:
            Instance of the Pydantic model
        """
        # Add schema instruction to system prompt
        schema_instruction = (
            "\n\nReturn a JSON object that matches this schema:\n"
            f"{json.dumps(model_class.model_json_schema(), indent=2)}"
        )
        full_system_prompt = system_prompt + schema_instruction
        
        response_dict = await self.call_with_json(
            system_prompt=full_system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens
        )
        
        return model_class(**response_dict)
    
    def format_context_chunks(
        self,
        chunks: list[Dict[str, Any]],
        label: str = "CONTEXT",
        max_items: Optional[int] = None
    ) -> str:
        """
        Format a list of context chunks into a readable string.
        
        Args:
            chunks: List of chunk dicts with 'content' key
            label: Label for the context section
            max_items: Maximum number of chunks to include
            
        Returns:
            Formatted string
        """
        if max_items:
            chunks = chunks[:max_items]
        
        if not chunks:
            return f"{label}: No context available"
        
        formatted = f"{label}:\n\n"
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            
            formatted += f"{label} {i}:\n{content}\n"
            
            # Add source info if available
            if metadata:
                source_info = []
                if 'filename' in metadata:
                    source_info.append(f"Source: {metadata['filename']}")
                if 'source_page' in metadata:
                    source_info.append(f"Page: {metadata['source_page']}")
                if source_info:
                    formatted += f"  [{', '.join(source_info)}]\n"
            
            formatted += "\n"
        
        return formatted