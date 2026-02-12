from typing import Literal
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Request model for generating quiz questions"""
    topic: str = Field(..., min_length=3, description="The topic to generate questions about")
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium", description="Question difficulty level")
    count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")


class QuestionResponse(BaseModel):
    """Response model for a single quiz question"""
    question: str = Field(..., description="The question text")
    options: dict[str, str] = Field(..., description="Answer options (A, B, C, D)")
    answer: str = Field(..., description="The correct answer key (A, B, C, or D)")
    explanation: str = Field(..., description="Explanation of the correct answer")
    difficulty: str = Field(..., description="Question difficulty level")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: str = "unknown"


class IngestRequest(BaseModel):
    """Request model for ingesting content"""
    source_type: Literal["textbook", "question"] = Field(..., description="Type of content being ingested")


class IngestResponse(BaseModel):
    """Response model for content ingestion"""
    chunks_processed: int
    embeddings_created: int
    images_processed: int = 0
    message: str
