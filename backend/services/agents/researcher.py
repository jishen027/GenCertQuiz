"""
Researcher Agent: Extracts core facts and specific formulas from textbook content.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from .base_agent import BaseAgent


class ResearchBrief(BaseModel):
    """Structured output from the Researcher agent."""
    topic: str
    difficulty: str
    core_facts: List[Dict[str, Any]]  # Each fact has text, importance, source
    key_definitions: List[Dict[str, str]]
    formulas_and_rules: List[Dict[str, str]]
    related_concepts: List[str]
    summary: str
    source_references: List[str]


class ResearcherAgent(BaseAgent):
    """
    The Researcher agent extracts core facts, definitions, and formulas
    from textbook content relevant to a given topic and difficulty level.
    
    This agent ensures factual accuracy by working directly with knowledge base content.
    """
    
    def __init__(self, retriever, **kwargs):
        """
        Initialize the Researcher agent.
        
        Args:
            retriever: HybridRetriever instance for fetching context
            **kwargs: Passed to BaseAgent
        """
        super().__init__(**kwargs)
        self.retriever = retriever
    
    async def research(
        self,
        topic: str,
        difficulty: str,
        max_facts: int = 6,
        max_context_chunks: int = 8
    ) -> ResearchBrief:
        """
        Conduct research on a topic at a specified difficulty level.
        
        Args:
            topic: The topic to research
            difficulty: Difficulty level (easy, medium, hard)
            max_facts: Maximum number of core facts to extract
            max_context_chunks: Maximum context chunks to retrieve
            
        Returns:
            ResearchBrief with extracted knowledge
        """
        # Step 1: Retrieve relevant content from knowledge base
        context_chunks = await self.retriever.fetch_facts(
            query=topic,
            limit=max_context_chunks
        )
        
        if not context_chunks:
            raise ValueError(f"No factual content found for topic: {topic}")
        
        # Step 2: Format context for LLM
        formatted_context = self.format_context_chunks(
            context_chunks,
            label="TEXTBOOK_CONTENT",
            max_items=None
        )
        
        # Step 3: Build prompts
        system_prompt = """You are an expert Researcher for a professional examination board. Your task is to extract and synthesize factual information from textbook content.

Your responsibilities:
1. Identify the most important core facts for the topic
2. Extract key definitions with clear wording
3. List any formulas, rules, or principles
4. Identify related concepts for context
5. Cite sources when available

For difficulty levels:
- EASY: Focus on fundamental concepts, basic definitions, direct facts
- MEDIUM: Include relationships between concepts, moderate complexity
- HARD: Include edge cases, exceptions, advanced nuances, interdependencies

CRITICAL: Only use information from the provided TEXTBOOK_CONTENT. Do not hallucinate or add external knowledge.
Be concise: keep fact statements under 30 words, definitions under 25 words, summaries under 50 words."""

        user_prompt = f"""Research the following topic and create a comprehensive research brief.

TOPIC: {topic}
DIFFICULTY LEVEL: {difficulty}

{formatted_context}

Return a JSON object with this structure:
{{
    "topic": "the topic",
    "difficulty": "easy|medium|hard",
    "core_facts": [
        {{
            "fact": "The factual statement",
            "importance": "high|medium|low",
            "source": "source reference if available"
        }}
    ],
    "key_definitions": [
        {{
            "term": "term name",
            "definition": "clear definition"
        }}
    ],
    "formulas_and_rules": [
        {{
            "name": "formula/rule name",
            "expression": "the formula or rule text"
        }}
    ],
    "related_concepts": ["concept1", "concept2", ...],
    "summary": "2-3 sentence summary of the topic",
    "source_references": ["source1", "source2", ...]
}}

Extract up to {max_facts} core facts, prioritized by relevance and importance."""

        # Step 4: Call LLM and parse response
        response_dict = await self.call_with_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,  # Lower temperature for factual accuracy
            max_completion_tokens=8192
        )
        
        return ResearchBrief(**response_dict)
    
    async def extract_formulas(
        self,
        topic: str,
        context_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Specifically extract formulas and rules for a topic.
        
        Args:
            topic: The topic
            context_chunks: Relevant context chunks
            
        Returns:
            List of formula/rule dicts
        """
        formatted_context = self.format_context_chunks(
            context_chunks,
            label="CONTENT",
            max_items=10
        )
        
        system_prompt = """You are an expert at identifying mathematical formulas, technical rules, and principles in educational content.

Extract ALL formulas, equations, rules, and principles from the provided content."""

        user_prompt = f"""Extract formulas and rules for: {topic}

{formatted_context}

Return JSON:
{{
    "formulas_and_rules": [
        {{
            "name": "name of formula/rule",
            "expression": "the formula or rule text",
            "description": "brief explanation of what it does"
        }}
    ]
}}"""

        response = await self.call_with_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )
        
        return response.get('formulas_and_rules', [])