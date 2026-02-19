"""
Topic Extractor Service.

Extracts topics from textbook content using the LLM, focusing on early
pages which typically contain the Table of Contents. Stores results in
the `topics` database table.
"""
import asyncpg
from typing import List, Dict, Any
from .agents.base_agent import BaseAgent


class TopicExtractor:
    """
    Extracts key topics from a textbook's content via LLM and persists
    them to the `topics` database table.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def extract_and_store(self, filename: str) -> List[str]:
        """
        Extract topics from a textbook and store them in the database.

        Fetches the first 30 text chunks for the given filename (preferring
        low page numbers, which typically contain the Table of Contents),
        sends them to an LLM, and persists the resulting topic list.

        Args:
            filename: The textbook filename as stored in knowledge_base metadata.

        Returns:
            List of topic name strings that were stored.
        """
        # 1. Fetch early-page text chunks for this file
        chunks = await self._fetch_early_chunks(filename, limit=30)
        if not chunks:
            print(f"  TopicExtractor: No chunks found for '{filename}'")
            return []

        # 2. Build context from chunks
        context_text = self._build_context(chunks)

        # 3. Call LLM to extract topics
        topics = await self._call_llm(filename, context_text)
        if not topics:
            print(f"  TopicExtractor: LLM returned no topics for '{filename}'")
            return []

        # 4. Store topics in DB (upsert to avoid duplicates)
        stored = await self._store_topics(filename, topics)
        print(f"  TopicExtractor: Stored {stored} topics for '{filename}'")
        return topics

    async def _fetch_early_chunks(self, filename: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieve the earliest text chunks for the given filename."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content, metadata
                FROM knowledge_base
                WHERE source_type = 'textbook'
                  AND metadata->>'filename' = $1
                ORDER BY
                    (metadata->>'source_page')::int ASC NULLS LAST,
                    created_at ASC
                LIMIT $2
                """,
                filename,
                limit,
            )
            return [{"content": row["content"], "metadata": dict(row["metadata"])} for row in rows]

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Concatenate chunk texts into a single context string."""
        parts = []
        for chunk in chunks:
            text = chunk.get("content", "").strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts[:30])  # limit to 30 chunks

    async def _call_llm(self, filename: str, context_text: str) -> List[str]:
        """Ask the LLM to extract topics from the textbook context."""
        agent = BaseAgent()

        system_prompt = (
            "You are an expert curriculum analyst. "
            "Given text from the beginning of a textbook (typically the table of contents or introductory chapters), "
            "extract a comprehensive list of the main subject topics covered. "
            "Return ONLY the topic names — no descriptions, no numbering. "
            "Each topic should be concise (2–6 words), distinct, and suitable as a quiz topic. "
            "Aim for 5–20 topics depending on the content. "
            'Return JSON in the format: {"topics": ["Topic A", "Topic B", ...]}'
        )

        user_prompt = (
            f"Extract the main topics from this textbook excerpt (filename: {filename}):\n\n"
            f"{context_text[:6000]}\n\n"
            "Return a JSON object with a 'topics' key containing a list of topic name strings."
        )

        try:
            result = await agent.call_with_json(system_prompt, user_prompt, temperature=0.3)
            raw_topics = result.get("topics", [])
            # Sanitize: ensure strings, strip whitespace, remove empties
            topics = [str(t).strip() for t in raw_topics if str(t).strip()]
            return topics
        except Exception as e:
            print(f"  TopicExtractor: LLM call failed: {e}")
            return []

    async def _store_topics(self, filename: str, topics: List[str]) -> int:
        """
        Insert topics into the DB, skipping duplicates (same name + filename).
        Returns the number of new rows inserted.
        """
        if not topics:
            return 0

        async with self.db_pool.acquire() as conn:
            count = 0
            for topic_name in topics:
                try:
                    result = await conn.execute(
                        """
                        INSERT INTO topics (name, source_filename)
                        VALUES ($1, $2)
                        ON CONFLICT (name, source_filename) DO NOTHING
                        """,
                        topic_name,
                        filename,
                    )
                    if result == "INSERT 0 1":
                        count += 1
                except Exception as e:
                    print(f"  TopicExtractor: Failed to store topic '{topic_name}': {e}")
            return count

    async def delete_topics_for_file(self, filename: str) -> int:
        """
        Delete all topics associated with a given textbook filename.

        Returns:
            Number of deleted rows.
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM topics WHERE source_filename = $1",
                filename,
            )
            deleted = int(result.replace("DELETE ", ""))
            print(f"  TopicExtractor: Deleted {deleted} topics for '{filename}'")
            return deleted
