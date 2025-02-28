import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple
import tempfile
from dataclasses import dataclass
try:
    import fitz  # PyMuPDF
except ImportError:
    from PyMuPDF import fitz
from app.agents.document_analyzer import DocumentAnalyzerAgent
from app.agents.grading_agent import GradingAgent
from app.agents.pdf_formatter import PDFFormattingAgent
from app.agents.quality_control import QualityControlAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GradingResult:
    """Results of grading an answer"""
    question_num: int
    score: int
    feedback: str
    is_correct: bool
    confidence: float = 1.0

class AgenticGradingService:
    def __init__(self):
        self.document_analyzer = DocumentAnalyzerAgent()
        self.grading_agent = GradingAgent()
        self.pdf_formatter = PDFFormattingAgent()
        self.quality_control = QualityControlAgent()
    
    def process_submission(
        self,
        student_pdf: Path,
        answer_key_pdf: Path,
        student_name: str
    ) -> Tuple[Path, Path, bool]:
        """
        Process a student submission using the agentic approach.
        Returns: (marked_pdf_path, report_path, quality_check_passed)
        """
        try:
            # Create temporary directory for output files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                
                # 1. Analyze document layout
                logger.info("Analyzing document layout...")
                layout_analysis = self.document_analyzer.analyze_layout(student_pdf)
                
                if not layout_analysis.question_regions:
                    raise Exception("No questions detected in the document")
                
                # 2. Extract and grade answers
                logger.info("Extracting and grading answers...")
                answers = self._extract_answers(student_pdf, layout_analysis)
                correct_answers = self._extract_answers(answer_key_pdf)
                
                if not answers:
                    raise Exception("No answers extracted from student submission")
                
                raw_grading_results = self.grading_agent.grade_submission(
                    answers,
                    correct_answers,
                    {}  # Default scoring rubric
                )
                
                # Convert raw results to GradingResult objects
                grading_results = [
                    GradingResult(
                        question_num=result["question_num"],
                        score=result["score"],
                        feedback=result["feedback"],
                        is_correct=result["is_correct"]
                    )
                    for result in raw_grading_results
                ]
                
                # 3. Create marked PDF
                logger.info("Creating marked PDF...")
                marked_pdf_path = temp_dir_path / f"{student_name}_marked.pdf"
                report_path = temp_dir_path / f"{student_name}_report.pdf"
                
                # First attempt at creating marked PDF
                self.pdf_formatter.create_marked_pdf(
                    student_pdf,
                    layout_analysis,
                    [
                        {
                            "question_num": result.question_num,
                            "feedback": result.feedback,
                            "is_correct": result.is_correct
                        }
                        for result in grading_results
                    ],
                    marked_pdf_path
                )
                
                # 4. Quality control check
                logger.info("Performing quality control check...")
                max_retries = 3
                retry_count = 0
                qc_result = None
                quality_check_passed = False
                
                while retry_count < max_retries:
                    qc_result = self.quality_control.verify_output(
                        marked_pdf_path,
                        [
                            {
                                "question_num": result.question_num,
                                "feedback": result.feedback,
                                "is_correct": result.is_correct
                            }
                            for result in grading_results
                        ]
                    )
                    
                    if qc_result.is_approved:
                        quality_check_passed = True
                        break
                    
                    # Log QC issues
                    logger.warning(f"Quality control issues (attempt {retry_count + 1}/{max_retries}):")
                    for issue in qc_result.issues:
                        logger.warning(f"- {issue}")
                    
                    # Try to fix issues
                    improved_pdf_path = temp_dir_path / f"{student_name}_marked_improved_{retry_count + 1}.pdf"
                    self.pdf_formatter.create_marked_pdf(
                        student_pdf,
                        layout_analysis,
                        [
                            {
                                "question_num": result.question_num,
                                "feedback": result.feedback,
                                "is_correct": result.is_correct
                            }
                            for result in grading_results
                        ],
                        improved_pdf_path,
                        qc_result.improvements
                    )
                    
                    # Replace original with improved version
                    if improved_pdf_path.exists():
                        marked_pdf_path.unlink(missing_ok=True)
                        improved_pdf_path.rename(marked_pdf_path)
                    
                    retry_count += 1
                
                # 5. Generate report
                logger.info("Generating report...")
                self._generate_report(
                    grading_results,
                    student_name,
                    report_path
                )
                
                # Copy files to output directory
                output_dir = Path("static/output")
                output_dir.mkdir(exist_ok=True, parents=True)
                
                final_marked_pdf = output_dir / f"{student_name}_marked.pdf"
                final_report_pdf = output_dir / f"{student_name}_report.pdf"
                
                import shutil
                shutil.copy2(marked_pdf_path, final_marked_pdf)
                shutil.copy2(report_path, final_report_pdf)
                
                return final_marked_pdf, final_report_pdf, quality_check_passed
                
        except Exception as e:
            logger.error(f"Error in agentic grading process: {str(e)}")
            raise
    
    def _extract_answers(
        self,
        pdf_path: Path,
        layout_analysis = None
    ) -> Dict[int, str]:
        """Extract answers from a PDF."""
        # If we have layout analysis, use it to extract answers more accurately
        if layout_analysis and hasattr(layout_analysis, 'question_regions'):
            answers = {}
            doc = fitz.open(str(pdf_path))
            
            try:
                for question in layout_analysis.question_regions:
                    if 'question_num' not in question or 'page' not in question or 'bbox' not in question:
                        logger.warning(f"Skipping malformed question region: {question}")
                        continue
                        
                    page = doc[question["page"]]
                    # Extract text from the question's bounds
                    text = page.get_text(
                        "text",
                        clip=question["bbox"]
                    )
                    answers[question["question_num"]] = text.strip()
                
                return answers
                
            finally:
                doc.close()
        else:
            # For answer key, use simpler text extraction
            doc = fitz.open(str(pdf_path))
            try:
                text = ""
                for page in doc:
                    text += page.get_text("text")
                
                # Use the grading agent to extract answers from text
                result = self.grading_agent._extract_answers({
                    "text": text,
                    "question_numbers": []  # Empty list to get all questions
                })
                
                if "error" in result:
                    raise Exception(result["error"])
                
                return result.get("answers", {})
                
            finally:
                doc.close()
    
    def _generate_report(
        self,
        grading_results: List[GradingResult],
        student_name: str,
        output_path: Path
    ):
        """Generate a detailed grading report."""
        doc = fitz.open()
        page = doc.new_page()
        
        # Add report header
        y = 50
        page.insert_text(
            (50, y),
            f"Grading Report for {student_name}",
            fontsize=16
        )
        
        y += 40
        page.insert_text(
            (50, y),
            "Question-by-Question Breakdown:",
            fontsize=12
        )
        
        # Add results for each question
        total_score = 0
        max_score = 0
        
        for result in grading_results:
            y += 30
            
            # Question header
            page.insert_text(
                (50, y),
                f"Question {result.question_num}:",
                fontsize=11
            )
            
            # Score
            page.insert_text(
                (150, y),
                f"Score: {result.score}/10",
                fontsize=11
            )
            
            # Feedback
            y += 20
            page.insert_text(
                (70, y),
                f"Feedback: {result.feedback}",
                fontsize=11
            )
            
            total_score += result.score
            max_score += 10
        
        # Add total score
        y += 40
        if max_score > 0:
            percentage = (total_score/max_score)*100
        else:
            percentage = 0
            
        page.insert_text(
            (50, y),
            f"Total Score: {total_score}/{max_score} ({percentage:.1f}%)",
            fontsize=14
        )
        
        # Save the report
        doc.save(str(output_path))
        doc.close() 