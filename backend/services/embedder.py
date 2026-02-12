"""
Embedding generation service using OpenAI API with text chunking.
"""
import os
import asyncio
from typing import List, Dict, Any, Optional
import asyncpg
from openai import AsyncOpenAI
import tiktoken


class EmbeddingService:
    """Generate and store embeddings for text chunks"""
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        """
        Initialize the embedding service.
        
        Args:
            db_pool: Database connection pool
            api_key: OpenAI API key (defaults to env var)
            model: Embedding model name
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Overlap tokens between chunks
        """
        self.db_pool = db_pool
        self.model = model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = AsyncOpenAI(api_key=api_key)
        
        # Initialize tokenizer for chunking
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for newer models
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks based on token count.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of text chunks
        """
        tokens = self.encoding.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Check if we've reached the end before updating start
            if end >= len(tokens):
                break
            
            # Move to next chunk with overlap
            start = end - self.chunk_overlap
        
        return chunks
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {str(e)}")
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise RuntimeError(f"Failed to generate batch embeddings: {str(e)}")
    
    async def store_chunk(
        self,
        content: str,
        embedding: List[float],
        source_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a chunk with its embedding in the database.
        
        Args:
            content: Text content
            embedding: Embedding vector
            source_type: Type of source ('textbook', 'question', 'diagram')
            metadata: Additional metadata as JSON
            
        Returns:
            UUID of the inserted record
        """
        # Convert embedding list to PostgreSQL vector format
        import json
        embedding_str = json.dumps(embedding)
        metadata_json = json.dumps(metadata or {})
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_base (content, embedding, source_type, metadata)
                VALUES ($1, $2::vector, $3, $4::jsonb)
                RETURNING id
                """,
                content,
                embedding_str,
                source_type,
                metadata_json
            )
            return str(row['id'])
    
    async def process_and_store(
        self,
        chunks: List[Dict[str, Any]],
        source_type: str
    ) -> Dict[str, int]:
        """
        Process chunks: generate embeddings and store in database.
        
        Args:
            chunks: List of chunk dicts from PDF parser
            source_type: Type of source ('textbook', 'question', 'diagram')
            
        Returns:
            Dict with processing statistics
        """
        stored_count = 0
        embedding_count = 0
        
        # Process in batches of 100 to avoid API limits
        batch_size = 100
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Extract text content
            texts = [chunk['content'] for chunk in batch]
            
            # Further chunk if needed
            all_chunk_texts = []
            chunk_metadata = []
            
            for idx, text in enumerate(texts):
                sub_chunks = self.chunk_text(text)
                for sub_chunk in sub_chunks:
                    all_chunk_texts.append(sub_chunk)
                    # Merge original metadata with chunk info
                    meta = batch[idx].get('metadata', {})
                    meta['original_index'] = i + idx
                    chunk_metadata.append(meta)
            
            # Generate embeddings in batch
            embeddings = await self.generate_embeddings_batch(all_chunk_texts)
            embedding_count += len(embeddings)
            
            # Store all chunks
            for text, embedding, metadata in zip(all_chunk_texts, embeddings, chunk_metadata):
                await self.store_chunk(text, embedding, source_type, metadata)
                stored_count += 1
        
        return {
            'chunks_stored': stored_count,
            'embeddings_generated': embedding_count
        }


# CLI interface for testing (instant - no dependencies)
if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("EMBEDDING SERVICE - CHUNKING DEMO")
    print("=" * 60)
    print("\nThis service provides:")
    print("  • Token-based text chunking (configurable size)")
    print("  • OpenAI embedding generation")
    print("  • Batch processing for efficiency")
    print("  • Direct pgvector storage")
    
    print("\n" + "-" * 60)
    print("CHUNKING CONCEPT (simplified demo)")
    print("-" * 60)
    
    test_text = """AWS S3 (Simple Storage Service) is an object storage service offering industry-leading scalability, data availability, security, and performance. It is designed to store and retrieve any amount of data from anywhere on the web."""
    
    # Simulate chunking by character count (normally done by tokens)
    chunk_size = 100
    overlap = 20
    chunks = []
    
    start = 0
    while start < len(test_text):
        end = min(start + chunk_size, len(test_text))
        chunks.append(test_text[start:end])
        if end >= len(test_text):  # Reached the end
            break
        start = end - overlap
    
    print(f"\n✓ Original text: {len(test_text)} characters")
    print(f"✓ Chunk size: {chunk_size} chars (normally 500 tokens)")
    print(f"✓ Overlap: {overlap} chars (normally 50 tokens)")
    print(f"✓ Result: {len(chunks)} chunks\n")
    
    for idx, chunk in enumerate(chunks, 1):
        preview = chunk[:60] + "..." if len(chunk) > 60 else chunk
        print(f"Chunk {idx}: {preview}")
    
    print("\n" + "=" * 60)
    print("To test with real embeddings, use: POST /ingest")
    print("=" * 60)
