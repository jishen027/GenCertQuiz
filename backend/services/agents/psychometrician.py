"""
Psychometrician Agent: Drafts questions by matching textbook facts with past paper style.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from .base_agent import BaseAgent
from .researcher import ResearchBrief


class DraftedQuestion(BaseModel):
    """Structured output from the Psychometrician agent."""
    question: str
    question_type: str  # single_select or multiple_selection
    options: Dict[str, str]  # A, B, C, D
    answer: str  # A, B, C, or D (or "A, C" for multiple selection)
    explanation: str
    difficulty: str
    distractor_reasoning: List[Dict[str, str]]  # Why each distractor is chosen
    topic: str
    cognitive_level: str  # recall, application, analysis, synthesis


class PsychometricianAgent(BaseAgent):
    """
    The Psychometrician agent drafts exam questions by combining:
    1. Factual accuracy from the ResearchBrief
    2. Linguistic style from past paper examples
    3. Psychometric principles for appropriate difficulty
    
    This agent ensures questions are not "too easy" or "hallucinated."
    """
    
    async def draft_question(
        self,
        research_brief: ResearchBrief,
        style_profile: Optional[Dict[str, Any]] = None,
        style_examples: Optional[List[Dict[str, Any]]] = None,
        difficulty: str = "medium",
        forced_question_type: Optional[str] = None
    ) -> DraftedQuestion:
        """
        Draft a single exam question based on research brief and style guidance.
        
        Args:
            research_brief: Factual content from Researcher agent
            style_profile: Extracted style profile from past papers
            style_examples: Sample questions for style reference
            difficulty: Target difficulty level
            forced_question_type: Force a specific question type (single_select or multiple_selection)
            
        Returns:
            DraftedQuestion with complete question structure
        """
        # Format research brief for LLM
        research_context = self._format_research_brief(research_brief)
        
        # Format style examples
        style_context = self._format_style_examples(style_examples) if style_examples else ""
        
        # Format style profile
        profile_context = self._format_style_profile(style_profile) if style_profile else ""
        
        # Build prompts
        # Determine type instructions
        type_instruction = "Determine if the question should be SINGLE_SELECT or MULTIPLE_SELECTION based on content."
        if forced_question_type == "single_select":
            type_instruction = "Create a SINGLE_SELECT question (one correct answer)."
        elif forced_question_type == "multiple_selection":
            type_instruction = "Create a MULTIPLE_SELECTION question (at least two correct answers). IMPORTANT: Append '(choice 2)' to the end of the question text."

        system_prompt = f"""You are a Senior Examiner and Psychometrician for a professional certification examination board. Your expertise includes:

1. QUESTION CRAFTING: Create exam-style multiple-choice questions that are challenging but fair
2. STYLE MIRRORING: Match the linguistic patterns, complexity, and tone of actual exam papers
3. PSYCHOMETRICS: Design distractors that test common misconceptions and partial understandings
4. COGNITIVE ALIGNMENT: Match questions to the appropriate cognitive level (recall, application, analysis, synthesis)

STRICT REQUIREMENTS:
- Use EXACTLY 4 options (A, B, C, D)
- {type_instruction}
- For SINGLE_SELECT: Only ONE correct answer
- For MULTIPLE_SELECTION: At least TWO correct answers AND append '(choice 2)' to question text
- Make distractors plausible but clearly wrong to knowledgeable candidates
- Distractors should reflect common student misconceptions
- Questions must be answerable from the provided RESEARCH_CONTENT
- Mirror the style of PAST_PAPER_EXAMPLES (sentence length, phrasing patterns, complexity)
- Include detailed explanation that references specific facts

DIFFICULTY GUIDELINES:
- EASY: Direct recall of facts, single-step reasoning, clear wording
- MEDIUM: Application of concepts, 2-3 step reasoning, some ambiguity
- HARD: Synthesis of multiple concepts, multi-step reasoning, nuanced distractors

CRITICAL: Never invent facts. Only use information from the RESEARCH_CONTENT."""

        user_prompt = f"""Draft a {difficulty} difficulty question.

TOPIC: {research_brief.topic}

{research_context}

{profile_context}

{style_context}

Returns the result as a JSON object (NOT the schema definition, but the actual data) with this structure:
{{
    "question": "Question text...",
    "question_type": "single_select" OR "multiple_selection",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "answer": "A" OR "A, C" (comma separated for multiple),
    "explanation": "...",
    "difficulty": "{difficulty}",
    "distractor_reasoning": [
        {{"option": "A", "reason": "..."}},
        {{"option": "B", "reason": "..."}},
        {{"option": "C", "reason": "..."}},
        {{"option": "D", "reason": "..."}}
    ],
    "topic": "{research_brief.topic}",
    "cognitive_level": "application"
}}

Create ONE question that:
- Tests understanding of the research content
- Uses a question stem similar to past papers
- Is appropriate for {difficulty} difficulty
- matches the requested type: {forced_question_type if forced_question_type else "any valid type"}"""

        # Call LLM and parse response
        return await self.call_with_pydantic(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_class=DraftedQuestion,
            temperature=0.7,  # Higher temperature for creative question drafting
            max_tokens=2048
        )
    
    async def revise_question(
        self,
        current_draft: DraftedQuestion,
        feedback: List[str],
        research_brief: ResearchBrief
    ) -> DraftedQuestion:
        """
        Revise a question based on critic feedback.
        
        Args:
            current_draft: The current drafted question
            feedback: List of issues/suggestions from the Critic
            research_brief: Research brief for reference
            
        Returns:
            Revised DraftedQuestion
        """
        research_context = self._format_research_brief(research_brief)
        
        feedback_text = "\n".join([f"- {f}" for f in feedback])
        
        system_prompt = """You are a Senior Examiner revising a question based on feedback.

Your task:
1. Address each piece of feedback
2. Improve the question without changing its core intent
3. Maintain style consistency with exam papers
4. Ensure factual accuracy based on research content"""

        user_prompt = f"""Revise this question based on the feedback.

CURRENT DRAFT:
{{
    "question": "{current_draft.question}",
    "question_type": "{current_draft.question_type}",
    "options": {current_draft.options},
    "answer": "{current_draft.answer}",
    "explanation": "{current_draft.explanation}"
}}

FEEDBACK TO ADDRESS:
{feedback_text}

{research_context}

Returns the revised result as a JSON object (NOT schema).

Ensure the revision:
- Fixes all identified issues
- Maintains factual accuracy
- Preserves the cognitive level
- Improves distractor quality"""

        return await self.call_with_pydantic(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_class=DraftedQuestion,
            temperature=0.6,
            max_tokens=2048
        )
    
    def _format_research_brief(self, brief: ResearchBrief) -> str:
        """Format ResearchBrief for LLM consumption."""
        sections = []
        
        sections.append("RESEARCH_CONTENT:")
        sections.append(f"Topic: {brief.topic}")
        sections.append(f"Difficulty: {brief.difficulty}")
        sections.append(f"Summary: {brief.summary}")
        sections.append("")
        
        if brief.core_facts:
            sections.append("CORE FACTS:")
            for i, fact in enumerate(brief.core_facts, 1):
                sections.append(f"{i}. {fact['fact']} (Importance: {fact.get('importance', 'medium')})")
            sections.append("")
        
        if brief.key_definitions:
            sections.append("KEY DEFINITIONS:")
            for definition in brief.key_definitions:
                sections.append(f"- {definition['term']}: {definition['definition']}")
            sections.append("")
        
        if brief.formulas_and_rules:
            sections.append("FORMULAS AND RULES:")
            for formula in brief.formulas_and_rules:
                sections.append(f"- {formula['name']}: {formula['expression']}")
            sections.append("")
        
        if brief.related_concepts:
            sections.append(f"RELATED CONCEPTS: {', '.join(brief.related_concepts)}")
            sections.append("")
        
        return "\n".join(sections)
    
    def _format_style_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format style examples for LLM consumption."""
        if not examples:
            return ""
        
        sections = ["PAST_PAPER_EXAMPLES:"]
        
        for i, example in enumerate(examples, 1):
            content = example.get('content', '')
            sections.append(f"\nEXAMPLE {i}:")
            sections.append(content)
        
        return "\n".join(sections)
    
    def _format_style_profile(self, profile: Dict[str, Any]) -> str:
        """Format style profile for LLM consumption."""
        if not profile:
            return ""
        
        sections = ["STYLE_PROFILE:"]
        
        if 'question_stems' in profile:
            sections.append(f"\nCommon Question Stems: {', '.join(profile['question_stems'])}")
        
        if 'avg_sentence_length' in profile:
            sections.append(f"Average Sentence Length: {profile['avg_sentence_length']:.1f} words")
        
        if 'distractor_patterns' in profile:
            sections.append(f"Distractor Patterns: {', '.join(profile['distractor_patterns'])}")
        
        if 'complexity' in profile:
            sections.append(f"Typical Complexity: {profile['complexity']}")
        
        if 'common_misconceptions' in profile:
            sections.append(f"\nCommon Student Misconceptions:")
            for misconception in profile['common_misconceptions']:
                sections.append(f"- {misconception}")
        
        return "\n".join(sections)