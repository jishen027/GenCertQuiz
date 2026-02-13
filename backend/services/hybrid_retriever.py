"""
Hybrid Retriever: Combines vector search and keyword search using Reciprocal Rank Fusion.
"""
import json
from typing import List, Dict, Any, Optional
import asyncpg


class HybridRetriever:
    """
    Hybrid retrieval system that combines vector search and keyword search
    using Reciprocal Rank Fusion (RRF) for better results.
    
    Vector search finds conceptually related topics.
    Keyword search finds specific terms and formulas.
    RRF merges both result sets with configurable weighting.
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embedding_service,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        k: int = 60  # RRF constant
    ):
        """
        Initialize the hybrid retriever.
        
        Args:
            db_pool: Database connection pool
            embedding_service: EmbeddingService instance for query embedding
            vector_weight: Weight for vector search results (0-1)
            keyword_weight: Weight for keyword search results (0-1)
            k: RRF constant (typically 60, higher = more emphasis on top results)
        """
        self.db_pool = db_pool
        self.embedding_service = embedding_service
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.k = k
    
    async def search(
        self,
        query: str,
        source_types: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and keyword search.
        
        Args:
            query: Search query
            source_types: List of source types to search (default: all)
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity for vector results
            
        Returns:
            List of merged results with combined scores
        """
        # Run both searches in parallel
        vector_results = await self._vector_search(
            query, source_types, similarity_threshold, limit * 2
        )
        keyword_results = await self._keyword_search(
            query, source_types, limit * 2
        )
        
        # Merge using Reciprocal Rank Fusion
        merged = self._rrf_merge(vector_results, keyword_results)
        
        # Sort by combined score and limit
        merged.sort(key=lambda x: x['combined_score'], reverse=True)
        
        return merged[:limit]
    
    async def fetch_facts(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve factual textbook content relevant to the query.
        
        Uses hybrid search prioritizing textbook and diagram sources.
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity score
            
        Returns:
            List of relevant textbook chunks
        """
        return await self.search(
            query=query,
            source_types=['textbook', 'diagram'],
            limit=limit,
            similarity_threshold=similarity_threshold
        )
    
    async def fetch_style_examples(
        self,
        query: str,
        limit: int = 3,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Fetch sample question styles from exam papers and existing questions.
        Prioritizes exam_paper source type for style reference.
        
        Args:
            query: Search query (topic)
            limit: Max results to return
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of style example dicts with content, metadata, similarity
        """
        results = await self.search(
            query=query,
            source_types=['exam_paper', 'question'],
            limit=limit * 2,
            similarity_threshold=similarity_threshold
        )
        
        # Prioritize exam_paper results
        exam_papers = [r for r in results if r.get('source_type') == 'exam_paper']
        other = [r for r in results if r.get('source_type') != 'exam_paper']
        
        prioritized = exam_papers + other
        return prioritized[:limit]
    
    async def _vector_search(
        self,
        query: str,
        source_types: Optional[List[str]],
        similarity_threshold: float,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using pgvector.
        
        Args:
            query: Search query
            source_types: List of source types to filter
            similarity_threshold: Minimum similarity score
            limit: Maximum results
            
        Returns:
            List of results with vector similarity scores
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query)
        embedding_str = json.dumps(query_embedding)
        
        # Build source type filter
        source_filter = ""
        params = [embedding_str, similarity_threshold]
        
        if source_types:
            placeholders = ','.join([f'${i + 3}' for i in range(len(source_types))])
            source_filter = f"AND source_type = ANY(ARRAY[{placeholders}])"
            params.extend(source_types)
        
        params.append(limit)
        
        async with self.db_pool.acquire() as conn:
            query_sql = f"""
                SELECT 
                    id,
                    content,
                    metadata,
                    source_type,
                    1 - (embedding <=> $1::vector) as similarity
                FROM knowledge_base
                WHERE 1 - (embedding <=> $1::vector) > $2
                    {source_filter}
                ORDER BY embedding <=> $1::vector
                LIMIT ${len(params)}
            """
            
            rows = await conn.fetch(query_sql, *params)
            
            return [
                {
                    'id': str(row['id']),
                    'content': row['content'],
                    'metadata': dict(row['metadata']),
                    'source_type': row['source_type'],
                    'similarity': float(row['similarity']),
                    'vector_rank': i + 1,
                    'keyword_rank': None,
                    'combined_score': 0.0
                }
                for i, row in enumerate(rows)
            ]
    
    async def _keyword_search(
        self,
        query: str,
        source_types: Optional[List[str]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Perform full-text keyword search using PostgreSQL tsvector.
        
        Args:
            query: Search query
            source_types: List of source types to filter
            limit: Maximum results
            
        Returns:
            List of results with keyword ranking scores
        """
        # Convert query to tsquery
        # Simple approach: use plainto_tsquery for natural language queries
        params = [query]
        
        # Build source type filter
        source_filter = ""
        if source_types:
            placeholders = ','.join([f'${i + 2}' for i in range(len(source_types))])
            source_filter = f"AND source_type = ANY(ARRAY[{placeholders}])"
            params.extend(source_types)
        
        params.append(limit)
        
        async with self.db_pool.acquire() as conn:
            query_sql = f"""
                SELECT 
                    id,
                    content,
                    metadata,
                    source_type,
                    ts_rank(tsv, plainto_tsquery('english', $1)) as rank
                FROM knowledge_base
                WHERE tsv @@ plainto_tsquery('english', $1)
                    {source_filter}
                ORDER BY rank DESC
                LIMIT ${len(params)}
            """
            
            rows = await conn.fetch(query_sql, *params)
            
            return [
                {
                    'id': str(row['id']),
                    'content': row['content'],
                    'metadata': dict(row['metadata']),
                    'source_type': row['source_type'],
                    'similarity': float(row['rank']),  # Use keyword rank as similarity
                    'vector_rank': None,
                    'keyword_rank': i + 1,
                    'combined_score': 0.0
                }
                for i, row in enumerate(rows)
            ]
    
    def _rrf_merge(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge results using Reciprocal Rank Fusion (RRF).
        
        RRF formula: score = w1 * (1 / (k + r1)) + w2 * (1 / (k + r2))
        
        Where:
        - r1, r2 are ranks from each search method
        - w1, w2 are weights for each method
        - k is a constant (typically 60)
        
        Args:
            vector_results: Results from vector search
            keyword_results: Results from keyword search
            
        Returns:
            Merged results with combined scores
        """
        # Create ID-indexed maps
        merged = {}
        
        # Process vector results
        for result in vector_results:
            result_id = result['id']
            vector_rank = result['vector_rank']
            
            if result_id not in merged:
                merged[result_id] = result.copy()
            
            # Calculate RRF score for vector search
            rrf_score = self.vector_weight * (1 / (self.k + vector_rank))
            merged[result_id]['combined_score'] += rrf_score
        
        # Process keyword results
        for result in keyword_results:
            result_id = result['id']
            keyword_rank = result['keyword_rank']
            
            if result_id not in merged:
                merged[result_id] = result.copy()
            else:
                # Add keyword rank if not already present
                merged[result_id]['keyword_rank'] = keyword_rank
            
            # Calculate RRF score for keyword search
            rrf_score = self.keyword_weight * (1 / (self.k + keyword_rank))
            merged[result_id]['combined_score'] += rrf_score
        
        # Convert back to list
        return list(merged.values())


# CLI test
if __name__ == "__main__":
    print("=" * 60)
    print("HYBRID RETRIEVER - ARCHITECTURE OVERVIEW")
    print("=" * 60)
    print("\n🔍 Dual Search Strategy:")
    print("  • Vector Search: Conceptual similarity via pgvector")
    print("  • Keyword Search: Exact term matching via PostgreSQL tsvector")
    print("\n🔄 Reciprocal Rank Fusion (RRF):")
    print("  • Merges both result sets")
    print("  • Formula: score = w1/(k+r1) + w2/(k+r2)")
    print("  • Configurable weights (default: 50/50)")
    print("  • k=60 (standard RRF constant)")
    print("\n📚 Specialized Methods:")
    print("  • fetch_facts() → textbook + diagram content")
    print("  • fetch_style_examples() → exam_paper + question content")
    print("\n" + "=" * 60)
    print("To test: Use POST /generate endpoint (after ingesting PDFs)")
    print("=" * 60)