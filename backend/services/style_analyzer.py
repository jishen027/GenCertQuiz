"""
Style Analyzer: Extracts style profiles from exam papers for psychometric guidance.
"""
from typing import Dict, Any, List, Optional
import re
import json
import asyncpg
from .agents.base_agent import BaseAgent


class StyleAnalyzer:
    """
    Analyzes exam papers to extract style profiles that guide question generation.
    
    Extracts:
    - Average sentence length
    - Common question stems (e.g., "Which of the following...")
    - Distractor patterns (how wrong answers are structured)
    - Complexity level (1-step vs multi-step reasoning)
    - Common trap patterns
    - Typical cognitive levels used
    """
    
    def __init__(self, db_pool: asyncpg.Pool, agent: Optional[BaseAgent] = None):
        """
        Initialize the style analyzer.
        
        Args:
            db_pool: Database connection pool
            agent: Optional BaseAgent for LLM-powered analysis
        """
        self.db_pool = db_pool
        self.agent = agent or BaseAgent()
    
    async def analyze_exam_paper(
        self,
        filename: str,
        topic_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a specific exam paper to extract its style profile.
        
        Args:
            filename: The filename of the exam paper
            topic_keywords: Optional list of topic keywords for classification
            
        Returns:
            Style profile dictionary
        """
        # Fetch all chunks from this exam paper
        chunks = await self._fetch_exam_paper_chunks(filename)
        
        if not chunks:
            raise ValueError(f"No chunks found for exam paper: {filename}")
        
        # Combine chunks into context
        context = self._combine_chunks(chunks)
        
        # Use LLM to analyze the style
        style_profile = await self._analyze_with_llm(context, topic_keywords)
        
        # Add metadata
        style_profile['source_filename'] = filename
        style_profile['chunk_count'] = len(chunks)
        
        # Cache in database
        await self._cache_style_profile(filename, topic_keywords or [], style_profile)
        
        return style_profile
    
    async def get_style_profile(
        self,
        topic: str,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get a style profile for a topic, using cache if available.
        
        Args:
            topic: The topic to get style profile for
            force_refresh: If True, bypass cache and re-analyze
            
        Returns:
            Style profile dict or None if not found
        """
        if not force_refresh:
            # Try to get from cache
            cached = await self._get_cached_profile(topic)
            if cached:
                return cached
        
        # Find relevant exam papers
        exam_papers = await self._find_relevant_exam_papers(topic)
        
        if not exam_papers:
            return None
        
        # Get the most relevant exam paper
        filename = exam_papers[0]['filename']
        
        # Analyze it
        return await self.analyze_exam_paper(filename, [topic])
    
    async def _fetch_exam_paper_chunks(
        self,
        filename: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch all chunks from a specific exam paper.
        
        Args:
            filename: The filename to fetch
            
        Returns:
            List of chunk dicts
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, content, metadata
                FROM knowledge_base
                WHERE source_type = 'exam_paper'
                    AND metadata->>'filename' = $1
                ORDER BY metadata->>'source_page' ASC, id ASC
                """,
                filename
            )
            
            return [
                {
                    'id': str(row['id']),
                    'content': row['content'],
                    'metadata': dict(row['metadata'])
                }
                for row in rows
            ]
    
    def _combine_chunks(self, chunks: List[Dict[str, Any]], max_chunks: int = 20) -> str:
        """
        Combine chunks into a single context string.
        
        Args:
            chunks: List of chunk dicts
            max_chunks: Maximum chunks to include
            
        Returns:
            Combined context string
        """
        chunks = chunks[:max_chunks]
        return "\n\n".join([chunk['content'] for chunk in chunks])
    
    async def _analyze_with_llm(
        self,
        context: str,
        topic_keywords: Optional[List[str]]
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze the style of exam paper content.
        
        Args:
            context: Combined exam paper content
            topic_keywords: Optional topic keywords
            
        Returns:
            Style profile dict
        """
        system_prompt = """You are an expert at analyzing examination papers to extract their question style and patterns. Your analysis will be used to guide AI-generated questions to match the style of real exams.

Analyze the provided exam paper content and extract:

1. QUESTION STEMS: Common ways questions start (e.g., "Which of the following...", "Identify the...", "What is the...", "Select the statement that...")

2. SENTENCE LENGTH: Average word count in question stems (short=10-15, medium=15-25, long=25+)

3. DISTRACTOR PATTERNS: How wrong answers are typically structured (e.g., "opposite of correct", "partially correct but missing detail", "common misconception", "unrelated technical term")

4. COMPLEXITY: Overall complexity level (simple=direct recall, moderate=requires application, complex=multi-step reasoning)

5. COMMON MISCONCEPTIONS: Any patterns in what students typically get wrong

6. COGNITIVE LEVELS: What levels of thinking are tested (recall, application, analysis, synthesis)

7. TRAP PATTERNS: Any common "tricks" used in the exam (e.g., "NOT" in question, "all of the above" options, subtle wording changes)"""

        user_prompt = f"""Analyze this exam paper content and extract its style profile.

{'TOPIC KEYWORDS: ' + ', '.join(topic_keywords) if topic_keywords else ''}

EXAM PAPER CONTENT:
{context[:10000]}  # Limit to 10k tokens

Return a JSON object with this structure:
{{
    "question_stems": ["stem1", "stem2", "stem3"],
    "avg_sentence_length": <number>,
    "sentence_length_category": "short|medium|long",
    "distractor_patterns": ["pattern1", "pattern2", "pattern3"],
    "complexity": "simple|moderate|complex",
    "common_misconceptions": ["misconception1", "misconception2"],
    "cognitive_levels": ["recall", "application", "analysis", "synthesis"],
    "trap_patterns": ["pattern1", "pattern2"],
    "tone": "formal|casual|technical",
    "option_count": 4,
    "notes": "Any additional observations about the style"
}}

Be specific and thorough in your analysis."""

        response = await self.agent.call_with_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=2048
        )
        
        return response
    
    async def _cache_style_profile(
        self,
        filename: str,
        topic_keywords: List[str],
        profile: Dict[str, Any]
    ) -> None:
        """
        Cache a style profile in the database.
        
        Args:
            filename: Source filename
            topic_keywords: Topic keywords
            profile: Style profile to cache
        """
        import json
        
        async with self.db_pool.acquire() as conn:
            # Check if profile already exists
            existing = await conn.fetchrow(
                "SELECT id FROM style_profiles WHERE source_filename = $1",
                filename
            )
            
            profile_json = json.dumps(profile)
            
            if existing:
                # Update existing
                await conn.execute(
                    """
                    UPDATE style_profiles
                    SET topic_keywords = $1,
                        profile = $2,
                        updated_at = NOW()
                    WHERE source_filename = $3
                    """,
                    topic_keywords,
                    profile_json,
                    filename
                )
            else:
                # Insert new
                await conn.execute(
                    """
                    INSERT INTO style_profiles (source_filename, topic_keywords, profile)
                    VALUES ($1, $2, $3)
                    """,
                    filename,
                    topic_keywords,
                    profile_json
                )
    
    async def _get_cached_profile(
        self,
        topic: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a cached style profile for a topic.
        
        Args:
            topic: The topic to search for
            
        Returns:
            Cached profile or None
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT profile, topic_keywords
                FROM style_profiles
                WHERE $1 = ANY(topic_keywords)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                topic.lower()
            )
            
            if not rows:
                return None
            
            profile_data = rows[0]['profile']
            if isinstance(profile_data, str):
                return json.loads(profile_data)
            return dict(profile_data)
    
    async def _find_relevant_exam_papers(
        self,
        topic: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find exam papers relevant to a topic.
        
        Args:
            topic: The topic to search for
            limit: Maximum results
            
        Returns:
            List of exam paper info dicts
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT 
                    metadata->>'filename' as filename,
                    COUNT(*) as chunk_count
                FROM knowledge_base
                WHERE source_type = 'exam_paper'
                    AND to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                GROUP BY metadata->>'filename'
                ORDER BY COUNT(*) DESC
                LIMIT $2
                """,
                topic,
                limit
            )
            
            return [
                {
                    'filename': row['filename'],
                    'chunk_count': row['chunk_count']
                }
                for row in rows
            ]
    
    async def analyze_all_exam_papers(self) -> Dict[str, Any]:
        """
        Analyze all exam papers in the database.
        
        Returns:
            Summary of analysis results
        """
        # Get all exam papers
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT metadata->>'filename' as filename
                FROM knowledge_base
                WHERE source_type = 'exam_paper'
                """
            )
        
        filenames = [row['filename'] for row in rows]
        
        results = {
            'total_exam_papers': len(filenames),
            'analyzed': 0,
            'failed': 0,
            'profiles': {}
        }
        
        for filename in filenames:
            try:
                profile = await self.analyze_exam_paper(filename)
                results['profiles'][filename] = profile
                results['analyzed'] += 1
            except Exception as e:
                print(f"Failed to analyze {filename}: {e}")
                results['failed'] += 1
        
        return results


# CLI test
if __name__ == "__main__":
    print("=" * 60)
    print("STYLE ANALYZER - ARCHITECTURE OVERVIEW")
    print("=" * 60)
    print("\n📊 Analysis Capabilities:")
    print("  • Question stems (common phrasing patterns)")
    print("  • Sentence length analysis")
    print("  • Distractor patterns (how wrong answers are structured)")
    print("  • Complexity assessment")
    print("  • Common misconceptions")
    print("  • Cognitive levels tested")
    print("  • Trap patterns")
    print("\n🗄️ Caching:")
    print("  • Profiles stored in style_profiles table")
    print("  • Indexed by topic keywords")
    print("  • Automatic refresh available")
    print("\n" + "=" * 60)
    print("To test: Call analyze_exam_paper() after ingesting exam papers")
    print("=" * 60)