"""
PDF export service for generating formatted question sheets.
"""
from typing import List, Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from io import BytesIO
from datetime import datetime


class PDFExporter:
    """Generate PDF documents from questions"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Create custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor='#4F46E5',
            spaceAfter=12,
            alignment=TA_CENTER
        ))
        
        # Question style
        self.styles.add(ParagraphStyle(
            name='Question',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor='#1F2937',
            spaceAfter=10,
            spaceBefore=10
        ))
        
        # Option style
        self.styles.add(ParagraphStyle(
            name='Option',
            parent=self.styles['Normal'],
            fontSize=11,
            leftIndent=20,
            spaceAfter=6
        ))
        
        # Answer style
        self.styles.add(ParagraphStyle(
            name='Answer',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor='#059669',
            leftIndent=20,
            spaceBefore=8
        ))
        
        # Explanation style
        self.styles.add(ParagraphStyle(
            name='Explanation',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor='#1E40AF',
            leftIndent=20,
            spaceBefore=6,
            spaceAfter=12
        ))
    
    def generate_pdf(
        self,
        questions: List[Dict[str, Any]],
        topic: str,
        difficulty: str
    ) -> BytesIO:
        """
        Generate a PDF from questions.
        
        Args:
            questions: List of question dictionaries
            topic: Exam topic
            difficulty: Question difficulty level
            
        Returns:
            BytesIO buffer containing the PDF
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build document content
        story = []
        
        # Title
        story.append(Paragraph(f"{topic.upper()}", self.styles['CustomTitle']))
        story.append(Paragraph(
            f"Exam Questions - {difficulty.capitalize()} Level",
            self.styles['Normal']
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y')}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.3*inch))
        
        # Questions
        for idx, q in enumerate(questions, 1):
            # Question number and text
            story.append(Paragraph(
                f"<b>Question {idx}:</b> {q['question']}",
                self.styles['Question']
            ))
            
            # Options
            for key, value in q['options'].items():
                is_correct = (key == q['answer'])
                option_text = f"<b>{key}.</b> {value}"
                if is_correct:
                    option_text += " <b>✓</b>"
                story.append(Paragraph(option_text, self.styles['Option']))
            
            # Answer
            story.append(Paragraph(
                f"<b>Correct Answer:</b> {q['answer']}",
                self.styles['Answer']
            ))
            
            # Explanation
            story.append(Paragraph(
                f"<b>Explanation:</b> {q['explanation']}",
                self.styles['Explanation']
            ))
            
            # Add page break every 3 questions (except last)
            if idx % 3 == 0 and idx < len(questions):
                story.append(PageBreak())
            else:
                story.append(Spacer(1, 0.2*inch))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer


# CLI test
if __name__ == "__main__":
    print("=" * 60)
    print("PDF EXPORTER - QUICK TEST")
    print("=" * 60)
    
    # Sample questions
    sample_questions = [
        {
            "question": "What is the capital of France?",
            "options": {
                "A": "London",
                "B": "Paris",
                "C": "Berlin",
                "D": "Madrid"
            },
            "answer": "B",
            "explanation": "Paris is the capital and largest city of France.",
            "difficulty": "easy"
        },
        {
            "question": "What is 2 + 2?",
            "options": {
                "A": "3",
                "B": "4",
                "C": "5",
                "D": "6"
            },
            "answer": "B",
            "explanation": "Basic arithmetic: 2 + 2 = 4",
            "difficulty": "easy"
        }
    ]
    
    exporter = PDFExporter()
    pdf_buffer = exporter.generate_pdf(sample_questions, "Sample Test", "easy")
    
    # Save to file for testing
    with open("test_output.pdf", "wb") as f:
        f.write(pdf_buffer.read())
    
    print("\n✓ PDF generated successfully!")
    print("✓ Saved as: test_output.pdf")
    print("=" * 60)
