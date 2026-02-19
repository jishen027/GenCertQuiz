"""
Multi-Agent RAG Engine for High-Quality Question Generation.

This module implements the complete multi-agent pipeline:
1. Researcher: Extracts core facts from textbook content
2. Psychometrician: Drafts questions matching exam style
3. Critic: Quality gate with reflection and iteration

The pipeline ensures questions are:
- Factual accurate (checked by Researcher and Critic)
- Style-consistent (guided by StyleAnalyzer and Psychometrician)
- High-quality (critiqued and iterated by Critic)
"""
import os
from typing import List, Dict, Any, Optional
import asyncpg

from .hybrid_retriever import HybridRetriever
from .style_analyzer import StyleAnalyzer
from .agents import ResearcherAgent, PsychometricianAgent, CriticAgent
from .agents.researcher import ResearchBrief
from .agents.psychometrician import DraftedQuestion


class MultiAgentRAGEngine:
    """
    Complete multi-agent RAG pipeline for high-quality question generation.
    
    Architecture:
    - HybridRetriever: Combines vector + keyword search for context retrieval
    - StyleAnalyzer: Extracts style profiles from past papers
    - Researcher Agent: Extracts core facts from textbook content
    - Psychometrician Agent: Drafts questions with style synthesis
    - Critic Agent: Quality gate with reflection and iteration
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embedding_service,
        similarity_threshold: float = 0.85,
        max_critic_iterations: int = 2,
        min_critic_score: int = 7
    ):
        """
        Initialize the multi-agent RAG engine.
        
        Args:
            db_pool: Database connection pool
            embedding_service: EmbeddingService instance
            similarity_threshold: Cosine similarity threshold for deduplication
            max_critic_iterations: Maximum revision loops with Critic
            min_critic_score: Minimum score required for Critic approval
        """
        self.db_pool = db_pool
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.max_critic_iterations = max_critic_iterations
        self.min_critic_score = min_critic_score
        
        # Initialize components
        self.retriever = HybridRetriever(db_pool, embedding_service)
        self.style_analyzer = StyleAnalyzer(db_pool)
        
        # Initialize agents
        self.researcher = ResearcherAgent(self.retriever)
        self.psychometrician = PsychometricianAgent()
        self.critic = CriticAgent()
    
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
        
        import json
        embedding_str = json.dumps(question_embedding)
        
        async with self.db_pool.acquire() as conn:
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
        topic: str = "",
        topics: Optional[List[str]] = None,
        count: int = 5,
        difficulty: str = "medium",
        max_total_attempts: int = 15,
        progress_callback: Optional[Any] = None,
        question_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple high-quality questions across one or more topics.

        When multiple topics are provided, questions are distributed across them
        in round-robin order so each topic gets roughly equal representation.

        Args:
            topic: Single topic string (legacy, for backward compat)
            topics: List of topic strings (preferred over `topic`)
            count: Number of questions to generate
            difficulty: Question difficulty (easy, medium, hard)
            max_total_attempts: Max total attempts (including retries)
            progress_callback: Async callback function(stage, message) for progress updates
            question_callback: Async callback function(question_dict) for streaming results

        Returns:
            List of generated questions with full metadata
        """
        # Resolve the final topics list
        if topics and len(topics) > 0:
            topic_list = [t.strip() for t in topics if t.strip()]
        elif topic:
            # Legacy: split on "; " in case the joined string was passed
            topic_list = [t.strip() for t in topic.split(";") if t.strip()]
        else:
            topic_list = ["General Knowledge"]

        if not topic_list:
            topic_list = ["General Knowledge"]

        async def report_progress(stage: str, message: str):
            if progress_callback:
                try:
                    await progress_callback(stage, message)
                except Exception as e:
                    print(f"Progress callback failed: {e}")

        async def report_question(question_data: Dict[str, Any]):
            if question_callback:
                try:
                    await question_callback(question_data)
                except Exception as e:
                    print(f"Question callback failed: {e}")

        display_topic = "; ".join(topic_list)
        print(f"\n{'='*60}")
        print(f"GENERATING {count} {difficulty.upper()} QUESTIONS ACROSS {len(topic_list)} TOPIC(S): {display_topic}")
        print(f"{'='*60}")

        await report_progress("init", f"Starting generation of {count} {difficulty} questions across {len(topic_list)} topic(s)")

        # Phase 1: Shared Style Ingestion (topic-agnostic)
        print("\n📚 Phase 1: Style Ingestion")
        print("-" * 40)
        print(f"  • Style Analyzer: Extracting style profile...")
        await report_progress("style", "Style Analyzer: Extracting patterns from past papers...")
        # Use first topic for style lookup (style is typically topic-agnostic in practice)
        style_profile = await self.style_analyzer.get_style_profile(topic_list[0])
        if style_profile:
            print(f"    ✓ Style profile extracted")
            await report_progress("style", "Style Analyzer: Profile extracted successfully")
        else:
            print(f"    ⚠ No style profile found (no exam papers ingested)")
            await report_progress("style", "Style Analyzer: No past papers found, using default style")

        style_examples = await self.retriever.fetch_style_examples(topic_list[0], limit=3)
        print(f"    ✓ Found {len(style_examples)} style examples")

        # Cache research briefs per topic to avoid re-fetching on retries
        research_cache: Dict[str, Any] = {}
        
        # Phase 2: Multi-Agent Generation Loop
        print(f"\n🤖 Phase 2: Multi-Agent Generation Loop")
        print("-" * 40)

        questions = []
        attempts = 0

        # Calculate how many multiple selection questions we need (20%)
        num_multi_questions = int(count * 0.2)
        generated_multi_count = 0

        while len(questions) < count and attempts < max_total_attempts:
            attempts += 1
            q_num = len(questions) + 1

            # Round-robin topic assignment so each topic gets equal coverage
            current_topic = topic_list[(q_num - 1) % len(topic_list)]
            print(f"\n  Question {q_num}/{count} — topic: '{current_topic}' (attempt {attempts})...")

            # Fetch (or reuse cached) research brief for this topic
            if current_topic not in research_cache:
                print(f"    • Researcher: Extracting facts for '{current_topic}'...")
                await report_progress("research", f"Researcher: Analyzing textbook content for '{current_topic}'...")
                try:
                    brief = await self.researcher.research(current_topic, difficulty)
                    research_cache[current_topic] = brief
                    print(f"      ✓ Found {len(brief.core_facts)} facts, {len(brief.key_definitions)} definitions")
                    await report_progress("research", f"Researcher: Found {len(brief.core_facts)} facts for '{current_topic}'")
                except Exception as e:
                    print(f"      ✗ Research failed for '{current_topic}': {e}")
                    await report_progress("error", f"Research failed for '{current_topic}': {e}")
                    continue

            research_brief = research_cache[current_topic]
            
            # Determine forced type for this question
            # If we still need multi-select questions, and the current slot suggests it's time, or if we are running out of slots
            remaining_slots = count - len(questions)
            remaining_multi_needed = num_multi_questions - generated_multi_count
            
            forced_type = "single_select"
            # Force multi-select if we still need them and:
            # 1. We're at a 5th interval (20% -> 1 in 5)
            # 2. Or we're running out of slots and must fill the quota
            if remaining_multi_needed > 0:
                if (q_num % 5 == 0) or (remaining_slots <= remaining_multi_needed):
                    forced_type = "multiple_selection"
            
            await report_progress("draft", f"Generating Question {q_num}/{count} ({forced_type})...")
            
            try:
                # Agent 2: Psychometrician drafts the question
                print(f"    • Psychometrician: Drafting question ({forced_type})...")
                await report_progress("draft", f"Psychometrician: Drafting question {q_num}...")
                draft = await self.psychometrician.draft_question(
                    research_brief=research_brief,
                    style_profile=style_profile,
                    style_examples=style_examples,
                    difficulty=difficulty,
                    forced_question_type=forced_type
                )
                print(f"      ✓ Draft created")
                print(f"        - Cognitive level: {draft.cognitive_level}")
                print(f"        - Distractor reasoning: {len(draft.distractor_reasoning)} distractors")
                
                # Agent 3: Critic reviews and iterates
                print(f"    • Critic: Reviewing question...")
                await report_progress("critic", f"Critic: Reviewing draft for quality and accuracy...")
                review = await self.critic.review(
                    question=draft,
                    research_brief=research_brief,
                    min_score=self.min_critic_score
                )
                
                # Revision loop
                current_draft = draft
                for iteration in range(self.max_critic_iterations):
                    if review.approved:
                        break
                    
                    print(f"      ⚠ Not approved (score: {review.score}/10)")
                    print(f"      • Psychometrician: Revising based on feedback...")
                    
                    await report_progress("revise", f"Psychometrician: Improving question (Critic score: {review.score}/10)...")
                    
                    current_draft = await self.psychometrician.revise_question(
                        current_draft=current_draft,
                        feedback=review.suggestions,
                        research_brief=research_brief
                    )
                    
                    # Re-review
                    review = await self.critic.review(
                        question=current_draft,
                        research_brief=research_brief,
                        min_score=self.min_critic_score
                    )
                
                if review.approved:
                    print(f"      ✓ Approved (score: {review.score}/10)")
                    await report_progress("approve", f"Critic: Question approved (Score: {review.score}/10)")
                else:
                    print(f"      ⚠ Not approved after {self.max_critic_iterations} revisions")
                    await report_progress("reject", f"Critic: Question rejected after revisions")
                    continue
                
                # Check for duplicates
                if await self.is_duplicate(current_draft.question):
                    print(f"    ⚠ Skipped (duplicate)")
                    await report_progress("skip", "Skipping duplicate question")
                    continue
                
                # Convert to response format
                question_dict = self._draft_to_response(current_draft, review)
                questions.append(question_dict)
                
                if question_dict.get('question_type') == 'multiple_selection':
                    generated_multi_count += 1
                
                print(f"    ✓ Question added")
                
                # Report success and stream question
                await report_progress("success", f"Question {q_num} generated successfully")
                await report_question(question_dict)
                
            except Exception as e:
                print(f"    ✗ Failed: {str(e)}")
                await report_progress("error", f"Error generating question: {str(e)}")
                continue
        
        # Summary
        print(f"\n{'='*60}")
        print(f"GENERATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Requested: {count}")
        print(f"  Generated: {len(questions)}")
        print(f"  Total attempts: {attempts}")
        print(f"  Success rate: {len(questions)/attempts*100:.1f}%")
        
        if not questions:
            print(f"\n⚠ WARNING: No questions generated!")
            print(f"   Tips:")
            print(f"   - Ensure textbook content is ingested for topic: {topic}")
            print(f"   - Ingest exam papers for better style matching")
            print(f"   - Try a broader topic or lower difficulty")
        
        return questions
    
    def _draft_to_response(
        self,
        draft: DraftedQuestion,
        review: "CritiqueReview"  # Forward reference
    ) -> Dict[str, Any]:
        """
        Convert a DraftedQuestion to the response format.
        
        Args:
            draft: The drafted question
            review: The critic review
            
        Returns:
            Question dict in response format
        """
        return {
            "question": draft.question,
            "question_type": draft.question_type,
            "options": draft.options,
            "answer": draft.answer,
            "explanation": draft.explanation,
            "difficulty": draft.difficulty,
            "distractor_reasoning": draft.distractor_reasoning,
            "topic": draft.topic,
            "cognitive_level": draft.cognitive_level,
            "quality_score": review.score,
            "quality_checks": review.checks,
            "source_references": []  # Could be populated from research brief
        }
    
    async def generate_questions_legacy(
        self,
        topic: str,
        count: int = 5,
        difficulty: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Legacy method for backward compatibility.
        
        Falls back to single-agent generation if multi-agent fails.
        """
        try:
            return await self.generate_questions(topic, count, difficulty)
        except Exception as e:
            print(f"Multi-agent pipeline failed: {e}")
            print("Falling back to legacy generation...")
            
            # Fallback to simple generation (imported from original)
            from .rag_engine_original import generate_questions_simple
            return await generate_questions_simple(
                topic=topic,
                count=count,
                difficulty=difficulty,
                retriever=self.retriever,
                embedding_service=self.embedding_service
            )


# Keep the original DualPathRetriever and QuestionGenerator for backward compatibility
from .embedder import EmbeddingService


class DualPathRetriever:
    """Retrieve context using separate paths for facts and question style"""
    
    def __init__(self, db_pool: asyncpg.Pool, embedding_service):
        self.db_pool = db_pool
        self.embedding_service = embedding_service
    
    async def fetch_facts(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Retrieve factual textbook content relevant to the query."""
        query_embedding = await self.embedding_service.generate_embedding(query)
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
                    'metadata': dict(row['metadata']),
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
        """Fetch sample question styles from exam papers."""
        query_embedding = await self.embedding_service.generate_embedding(query)
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
                    'metadata': dict(row['metadata']),
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
        """Generate a single exam question."""
        facts_context = "\n\n".join([f"FACT {i+1}:\n{fact}" for i, fact in enumerate(facts)])
        
        style_context = ""
        if style_examples:
            style_context = "\n\nEXAMPLE QUESTIONS FOR STYLE REFERENCE:\n" + \
                           "\n\n".join([f"EXAMPLE {i+1}:\n{ex}" for i, ex in enumerate(style_examples)])
        
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
            
            import json
            response_text = response.choices[0].message.content
            question_data = json.loads(response_text)
            return question_data
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate question: {str(e)}")


# Legacy RAGEngine for backward compatibility
class RAGEngine:
    """Legacy RAG engine - use MultiAgentRAGEngine instead"""
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embedding_service,
        similarity_threshold: float = 0.85
    ):
        self.retriever = DualPathRetriever(db_pool, embedding_service)
        self.generator = QuestionGenerator()
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.db_pool = db_pool
    
    async def is_duplicate(self, question_text: str, source_type: str = 'question') -> bool:
        question_embedding = await self.embedding_service.generate_embedding(question_text)
        import json
        embedding_str = json.dumps(question_embedding)
        
        async with self.db_pool.acquire() as conn:
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
        facts = await self.retriever.fetch_facts(topic, limit=10)
        style_examples = await self.retriever.fetch_style(topic, limit=3)
        
        if not facts:
            raise ValueError(f"No factual content found for topic: {topic}")
        
        fact_texts = [f['content'] for f in facts]
        style_texts = [s['content'] for s in style_examples] if style_examples else None
        
        questions = []
        attempts = 0
        max_total_attempts = count * max_retries
        
        while len(questions) < count and attempts < max_total_attempts:
            attempts += 1
            
            try:
                question = await self.generator.generate_question(
                    topic, fact_texts, style_texts, difficulty
                )
                
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
    print("MULTI-AGENT RAG ENGINE - ARCHITECTURE OVERVIEW")
    print("=" * 60)
    print("\n🤖 THREE-AGENT ARCHITECTURE:")
    print("  1. RESEARCHER → Extracts core facts from textbook")
    print("  2. PSYCHOMETRICIAN → Drafts questions with style synthesis")
    print("  3. CRITIC → Quality gate with reflection & iteration")
    print("\n🔍 HYBRID RETRIEVAL:")
    print("  • Vector Search (conceptual similarity)")
    print("  • Keyword Search (exact term matching)")
    print("  • RRF merging for optimal results")
    print("\n📊 STYLE ANALYSIS:")
    print("  • Extracts question stems, sentence length")
    print("  • Identifies distractor patterns")
    print("  • Caches profiles for reuse")
    print("\n✅ QUALITY GUARANTEES:")
    print("  • Factual accuracy (checked by Researcher + Critic)")
    print("  • Style consistency (guided by StyleAnalyzer)")
    print("  • Iterative refinement (Critic → Psychometrician loop)")
    print("\n" + "=" * 60)
    print("To test: Use POST /generate endpoint (after ingesting PDFs)")
    print("=" * 60)