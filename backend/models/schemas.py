from typing import Literal, Dict, Any, List, Optional
from pydantic import BaseModel, Field



class QuestionRequest(BaseModel):
    """Request model for generating quiz questions"""
    topics: List[str] = Field(
        ...,
        min_length=1,
        description="List of topics to generate questions about (at least one required)"
    )
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium", description="Question difficulty level")
    count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")

    @property
    def topic(self) -> str:
        """Combine selected topics into a single string for the generation pipeline."""
        return "; ".join(t.strip() for t in self.topics if t.strip())


class ExportRequest(BaseModel):
    """Request model for exporting questions to PDF"""
    questions: List[Dict[str, Any]] = Field(..., description="List of questions to export")
    topic: str = Field(..., description="Topic of the quiz")
    difficulty: str = Field(..., description="Difficulty level")


class QuestionResponse(BaseModel):
    """Response model for a single quiz question (original format)"""
    question: str = Field(..., description="The question text")
    options: Dict[str, str] = Field(..., description="Answer options (A, B, C, D)")
    answer: str = Field(..., description="The correct answer key (A, B, C, or D)")
    explanation: str = Field(..., description="Explanation of the correct answer")
    difficulty: str = Field(..., description="Question difficulty level")


class QuestionResponseV2(BaseModel):
    """Enhanced response model for multi-agent generated questions"""
    question: str = Field(..., description="The question text")
    options: Dict[str, str] = Field(..., description="Answer options (A, B, C, D)")
    answer: str = Field(..., description="The correct answer key (A, B, C, or D)")
    explanation: str = Field(..., description="Explanation of the correct answer")
    difficulty: str = Field(..., description="Question difficulty level")
    
    # Multi-agent metadata
    distractor_reasoning: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Why each distractor was chosen - what misconception it tests"
    )
    topic: str = Field(..., description="The topic this question covers")
    question_type: Literal["single_select", "multiple_selection"] = Field(
        default="single_select",
        description="Type of question: single_select (one answer) or multiple_selection (multiple answers)"
    )
    cognitive_level: str = Field(
        ...,
        description="Cognitive level: recall, application, analysis, or synthesis"
    )
    quality_score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Quality score from the Critic agent"
    )
    quality_checks: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Detailed quality check results from the Critic agent"
    )
    source_references: List[str] = Field(
        default_factory=list,
        description="Source references from the textbook"
    )


class GenerationMetadata(BaseModel):
    """Metadata about the question generation process"""
    topic: str
    difficulty: str
    questions_requested: int
    questions_generated: int
    total_attempts: int
    success_rate: float
    research_brief_facts: int = 0
    style_profile_available: bool = False
    style_examples_count: int = 0


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: str = "unknown"


class IngestRequest(BaseModel):
    """Request model for ingesting content"""
    source_type: Literal["textbook", "question", "exam_paper", "diagram"] = Field(
        ...,
        description="Type of content being ingested"
    )


class IngestResponse(BaseModel):
    """Response model for content ingestion"""
    chunks_processed: int
    embeddings_created: int
    images_processed: int = 0
    topics_extracted: int = 0
    message: str


class StyleProfile(BaseModel):
    """Style profile extracted from exam papers"""
    question_stems: List[str] = Field(
        default_factory=list,
        description="Common question stems used in the exam"
    )
    avg_sentence_length: float = Field(
        default=0.0,
        description="Average sentence length in words"
    )
    sentence_length_category: str = Field(
        default="medium",
        description="short | medium | long"
    )
    distractor_patterns: List[str] = Field(
        default_factory=list,
        description="How wrong answers are typically structured"
    )
    complexity: str = Field(
        default="moderate",
        description="simple | moderate | complex"
    )
    common_misconceptions: List[str] = Field(
        default_factory=list,
        description="Common student misconceptions identified"
    )
    cognitive_levels: List[str] = Field(
        default_factory=list,
        description="Cognitive levels tested: recall, application, analysis, synthesis"
    )
    trap_patterns: List[str] = Field(
        default_factory=list,
        description="Common trap/trick patterns in the exam"
    )
    tone: str = Field(
        default="formal",
        description="formal | casual | technical"
    )
    option_count: int = Field(default=4, description="Number of options typically used")


class FileInfo(BaseModel):
    """Information about an uploaded file"""
    name: str
    source_type: str
    chunks: int


class FilesResponse(BaseModel):
    """Response model for listing uploaded files"""
    textbooks: List[FileInfo] = Field(default_factory=list)
    exam_papers: List[FileInfo] = Field(default_factory=list)


class TopicItem(BaseModel):
    """A single extracted topic"""
    id: str
    name: str
    source_filename: str


class TopicsListResponse(BaseModel):
    """Response model for listing all available topics"""
    topics: List[TopicItem] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Result of style analysis on an exam paper"""
    source_filename: str
    chunk_count: int
    profile: StyleProfile


class ExamSystemOption(BaseModel):
    """Option model for exam system format"""
    id: int
    content: str


class QuestionResponseExamSystem(BaseModel):
    """Response model for exam system format"""
    id: int
    question: str
    options: List[ExamSystemOption]
    correct_answers: List[int]
    explanation: str
    domain: str
    tags: List[str]
