"""
RAG engine with dual-path retrieval and question generation.
"""
import os
from typing import List, Dict, Any, Optional
import asyncpg
import numpy as np


class DualPathRetriever:
    """Retrieve context using separate paths for facts and question style"""
    
    def __init__(self, db_pool: asyncpg.Pool, embedding_service):
        """
        Initialize the dual-path retriever.
        
        Args:
            db_pool: Database connection pool
            embedding_service: EmbeddingService instance for query embedding
        """
        self.db_pool = db_pool
        self.embedding_service = embedding_service
    
    async def fetch_facts(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve factual textbook content relevant to the query.
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity score
            
        Returns:
            List of relevant textbook chunks
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        # Convert to JSON string for PostgreSQL
        import json
        embedding_str = json.dumps(query_embedding)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    content,
                    metadata,
                    1 - (embedding <=> $1::vector) as similarity
                FROM knowledge_base
                WHERE source_type IN ('textbook', 'diagram')
                    AND 1 - (embedding <=> $1::vector) > $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                embedding_str,
                similarity_threshold,
                limit
            )
            
            return [
                {
                    'content': row['content'],
                    'metadata': row['metadata'],
                    'similarity': float(row['similarity'])
                }
                for row in rows
            ]
    
    async def fetch_style(
        self,
        query: str,
        similarity_threshold: float = 0.7,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Fetch sample question styles from exam papers and existing questions.
        Prioritizes exam_paper source type for style reference.
        
        Args:
            query: Search query (topic)
            similarity_threshold: Minimum similarity score
            limit: Max results to return
            
        Returns:
            List of style example dicts with content, metadata, similarity
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        # Convert to JSON string for PostgreSQL
        import json
        embedding_str = json.dumps(query_embedding)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    content,
                    metadata,
                    source_type,
                    1 - (embedding <=> $1::vector) as similarity
                FROM knowledge_base
                WHERE source_type IN ('exam_paper', 'question')
                    AND 1 - (embedding <=> $1::vector) > $2
                ORDER BY 
                    CASE 
                        WHEN source_type = 'exam_paper' THEN 0
                        ELSE 1
                    END,
                    embedding <=> $1::vector
                LIMIT $3
                """,
                embedding_str,
                similarity_threshold,
                limit
            )
            
            return [
                {
                    'content': row['content'],
                    'metadata': row['metadata'],
                    'similarity': float(row['similarity']),
                    'source_type': row['source_type']
                }
                for row in rows
            ]


class QuestionGenerator:
    """Generate exam questions using OpenAI GPT-4"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o"
    ):
        """
        Initialize the question generator.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
            model: OpenAI model to use (gpt-4o, gpt-4-turbo, etc.)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided")
        
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def generate_question(
        self,
        topic: str,
        facts: List[str],
        style_examples: Optional[List[str]] = None,
        difficulty: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate a single exam question.
        
        Args:
            topic: Question topic
            facts: Factual content chunks from textbook
            style_examples: Optional sample questions for style reference
            difficulty: Question difficulty (easy, medium, hard)
            
        Returns:
            Dict with question, options, answer, explanation, difficulty
        """
        # Build context
        facts_context = "\n\n".join([f"FACT {i+1}:\n{fact}" for i, fact in enumerate(facts)])
        
        style_context = ""
        if style_examples:
            style_context = "\n\nEXAMPLE QUESTIONS FOR STYLE REFERENCE:\n" + \
                           "\n\n".join([f"EXAMPLE {i+1}:\n{ex}" for i, ex in enumerate(style_examples)])
        
        # Build prompt
        system_prompt = f"""You are an expert certification exam question writer. Generate high-quality, exam-style multiple-choice questions based on the provided facts.

REQUIREMENTS:
- Create realistic, exam-level questions ({difficulty} difficulty)
- Use EXACTLY 4 options (A, B, C, D)
- Only ONE correct answer
- Make distractors plausible but clearly wrong
- Include detailed explanation
- Format as valid JSON

FACTS FROM TEXTBOOK:
{facts_context}
{style_context}"""

        user_prompt = f"""Generate ONE {difficulty} difficulty question about: {topic}

Return ONLY valid JSON in this exact format:
{{
    "question": "Question text here?",
    "options": {{
        "A": "First option",
        "B": "Second option",
        "C": "Third option",
        "D": "Fourth option"
    }},
    "answer": "B",
    "explanation": "Detailed explanation why B is correct and others are wrong",
    "difficulty": "{difficulty}"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            # Extract JSON from response
            import json
            response_text = response.choices[0].message.content
            question_data = json.loads(response_text)
            return question_data
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate question: {str(e)}")


class RAGEngine:
    """Complete RAG pipeline with deduplication"""
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embedding_service,
        similarity_threshold: float = 0.85
    ):
        """
        Initialize the RAG engine.
        
        Args:
            db_pool: Database connection pool
            embedding_service: EmbeddingService instance
            similarity_threshold: Cosine similarity threshold for deduplication
        """
        self.retriever = DualPathRetriever(db_pool, embedding_service)
        self.generator = QuestionGenerator()
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.db_pool = db_pool
    
    async def is_duplicate(
        self,
        question_text: str,
        source_type: str = 'question'
    ) -> bool:
        """
        Check if a similar question already exists.
        
        Args:
            question_text: Question to check
            source_type: Type filter for comparison
            
        Returns:
            True if duplicate found, False otherwise
        """
        # Generate embedding for new question
        question_embedding = await self.embedding_service.generate_embedding(question_text)
        
        # Convert to JSON string for PostgreSQL
        import json
        embedding_str = json.dumps(question_embedding)
        
        async with self.db_pool.acquire() as conn:
            # Find most similar existing question
            result = await conn.fetchrow(
                """
                SELECT 1 - (embedding <=> $1::vector) as similarity
                FROM knowledge_base
                WHERE source_type = $2
                ORDER BY embedding <=> $1::vector
                LIMIT 1
                """,
                embedding_str,
                source_type
            )
            
            if result and result['similarity'] >= self.similarity_threshold:
                return True
            
            return False
    
    async def generate_questions(
        self,
        topic: str,
        count: int = 5,
        difficulty: str = "medium",
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple unique questions on a topic.
        
        Args:
            topic: Question topic
            count: Number of questions to generate
            difficulty: Question difficulty
            max_retries: Max retries per question if duplicate
            
        Returns:
            List of generated questions
        """
        # Retrieve context
        facts = await self.retriever.fetch_facts(topic, limit=10)
        style_examples = await self.retriever.fetch_style(topic, limit=3)
        
        if not facts:
            raise ValueError(f"No factual content found for topic: {topic}")
        
        # Extract text content
        fact_texts = [f['content'] for f in facts]
        style_texts = [s['content'] for s in style_examples] if style_examples else None
        
        questions = []
        attempts = 0
        max_total_attempts = count * max_retries
        
        while len(questions) < count and attempts < max_total_attempts:
            attempts += 1
            
            try:
                # Generate question
                question = await self.generator.generate_question(
                    topic,
                    fact_texts,
                    style_texts,
                    difficulty
                )
                
                # Check for duplicates
                is_dup = await self.is_duplicate(question['question'])
                
                if not is_dup:
                    questions.append(question)
                else:
                    print(f"  Skipped duplicate question (attempt {attempts})")
                    
            except Exception as e:
                print(f"  Failed to generate question: {e}")
                continue
        
        return questions


# CLI test
if __name__ == "__main__":
    print("=" * 60)
    print("RAG ENGINE - ARCHITECTURE OVERVIEW")
    print("=" * 60)
    print("\n📚 Dual-Path Retrieval:")
    print("  • fetch_facts() → Textbook + diagram content")
    print("  • fetch_style() → Sample question patterns")
    print("\n🤖 Question Generation:")
    print("  • OpenAI GPT-4 with JSON mode")
    print("  • JSON-structured output")
    print("  • Configurable difficulty levels")
    print("\n🔍 Semantic Deduplication:")
    print("  • Cosine similarity threshold: 0.85")
    print("  • Prevents duplicate questions")
    print("\n" + "=" * 60)
    print("To test: Use POST /generate endpoint (after ingesting PDFs)")
    print("=" * 60)
