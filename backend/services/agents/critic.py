"""
Critic Agent: Quality gate with reflection and iteration.
"""
from typing import Dict, Any, List
from pydantic import BaseModel
from .base_agent import BaseAgent
from .researcher import ResearchBrief
from .psychometrician import DraftedQuestion


class CritiqueReview(BaseModel):
    """Structured output from the Critic agent."""
    approved: bool
    score: int  # 1-10 quality score
    issues: List[str]  # List of identified issues
    suggestions: List[str]  # Specific suggestions for improvement
    checks: Dict[str, Dict[str, Any]]  # Detailed check results


class CriticAgent(BaseAgent):
    """
    The Critic agent acts as a "Quality Gate" for drafted questions.
    
    It checks:
    1. Factual accuracy against the research brief
    2. Distractor plausibility
    3. No answer giveaway in question structure
    4. Difficulty alignment
    5. Clarity and unambiguity
    
    If not approved, it provides specific feedback for revision.
    """
    
    async def review(
        self,
        question: DraftedQuestion,
        research_brief: ResearchBrief,
        min_score: int = 7
    ) -> CritiqueReview:
        """
        Review a drafted question for quality.
        
        Args:
            question: The drafted question to review
            research_brief: Research brief to verify factual accuracy
            min_score: Minimum score required for approval
            
        Returns:
            CritiqueReview with approval decision and feedback
        """
        # Format content for LLM
        question_text = self._format_question(question)
        research_context = self._format_research_brief(research_brief)
        
        system_prompt = """You are a Senior Quality Assurance Specialist for a professional examination board. Your role is to critically evaluate multiple-choice questions.

Your evaluation criteria:

1. FACTUAL ACCURACY (CRITICAL)
   - Is the correct answer actually correct based on the research content?
   - Are all facts in the question and options accurate?
   - No hallucinations or external knowledge

2. DISTRACTOR QUALITY
   - Are distractors plausible but clearly wrong to knowledgeable candidates?
   - Do distractors test common misconceptions?
   - Is the answer count correct (1 for SINGLE_SELECT, >1 for MULTIPLE_SELECTION)?

3. NO ANSWER GIVEAWAY
   - Does the question structure accidentally reveal the answer?
   - Are there linguistic clues that point to the correct option?
   - Are options balanced in length and structure?

4. DIFFICULTY ALIGNMENT
   - Does the question match the stated difficulty level?
   - EASY: Direct recall, single-step
   - MEDIUM: Application, 2-3 step reasoning
   - HARD: Synthesis, multi-step reasoning

5. CLARITY
   - Is the question unambiguous?
   - Is the wording precise and clear?
   - Could multiple interpretations exist?

SCORING:
- 10: Perfect, no issues
- 8-9: Excellent, minor improvements possible
- 7: Good, acceptable with minor issues
- 5-6: Fair, needs revision
- 1-4: Poor, major issues or errors

APPROVAL:
- APPROVE if score >= {min_score} AND no critical factual errors
- REJECT if score < {min_score} OR any factual inaccuracy"""

        user_prompt = f"""Review this question critically.

{question_text}

{research_context}

Return a JSON object with this structure:
{{
    "approved": true/false,
    "score": 1-10,
    "issues": [
        "Specific issue 1",
        "Specific issue 2"
    ],
    "suggestions": [
        "Specific suggestion 1",
        "Specific suggestion 2"
    ],
    "checks": {{
        "factual_accuracy": {{
            "passed": true/false,
            "notes": "Specific notes about accuracy"
        }},
        "distractor_quality": {{
            "passed": true/false,
            "notes": "Notes about distractor plausibility"
        }},
        "no_answer_giveaway": {{
            "passed": true/false,
            "notes": "Notes about potential giveaways"
        }},
        "difficulty_alignment": {{
            "passed": true/false,
            "notes": "Notes about difficulty match"
        }},
        "clarity": {{
            "passed": true/false,
            "notes": "Notes about question clarity"
        }}
    }}
}}

Be specific and thorough in your evaluation. If a check fails, explain exactly why and suggest improvements."""

        response_dict = await self.call_with_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,  # Lower temperature for consistent evaluation
            max_tokens=2048
        )
        
        review = CritiqueReview(**response_dict)
        
        # Override approval if score is below threshold
        if review.score < min_score:
            review.approved = False
            review.issues.append(f"Quality score {review.score} is below minimum {min_score}")
        
        return review
    
    def _format_question(self, question: DraftedQuestion) -> str:
        """Format DraftedQuestion for LLM consumption."""
        sections = ["DRAFTED QUESTION:"]
        sections.append(f"Question: {question.question}")
        sections.append(f"Type: {question.question_type}")
        sections.append(f"Difficulty: {question.difficulty}")
        sections.append(f"Cognitive Level: {question.cognitive_level}")
        sections.append("")
        
        sections.append("Options:")
        correct_answers = [a.strip() for a in question.answer.split(',')]
        for key, value in question.options.items():
            marker = " ✓ (CORRECT)" if key in correct_answers else ""
            sections.append(f"  {key}. {value}{marker}")
        sections.append("")
        
        sections.append(f"Correct Answer: {question.answer}")
        sections.append("")
        
        sections.append(f"Explanation: {question.explanation}")
        sections.append("")
        
        if question.distractor_reasoning:
            sections.append("Distractor Reasoning:")
            for dr in question.distractor_reasoning:
                opt = dr.get('option', '?')
                reason = dr.get('reason', 'No reason provided')
                sections.append(f"  Option {opt}: {reason}")
            sections.append("")
        
        return "\n".join(sections)
    
    def _format_research_brief(self, brief: ResearchBrief) -> str:
        """Format ResearchBrief for LLM consumption."""
        sections = ["RESEARCH_BRIEF (for factual verification):"]
        sections.append(f"Topic: {brief.topic}")
        sections.append(f"Summary: {brief.summary}")
        sections.append("")
        
        if brief.core_facts:
            sections.append("Core Facts:")
            for fact in brief.core_facts:
                sections.append(f"  - {fact['fact']}")
            sections.append("")
        
        if brief.key_definitions:
            sections.append("Key Definitions:")
            for definition in brief.key_definitions:
                sections.append(f"  - {definition['term']}: {definition['definition']}")
            sections.append("")
        
        if brief.formulas_and_rules:
            sections.append("Formulas and Rules:")
            for formula in brief.formulas_and_rules:
                sections.append(f"  - {formula['name']}: {formula['expression']}")
            sections.append("")
        
        return "\n".join(sections)