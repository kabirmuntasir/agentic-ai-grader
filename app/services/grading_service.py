from pathlib import Path
from typing import Tuple, Dict, List
from .pdf_service import PDFService
from .gemini_service import GeminiService
import os
import fitz

class GradingService:
    def __init__(self):
        self.pdf_service = PDFService()
        self.gemini_service = GeminiService()
    
    def process_submission(
        self,
        student_paper_path: Path,
        answer_key_path: Path,
        student_name: str
    ) -> Tuple[Path, Path]:
        """
        Process a student's submission and return paths to marked PDF and report.
        Returns: (marked_pdf_path, report_path)
        """
        try:
            # Extract text from both PDFs
            student_text = self.pdf_service.extract_text_from_pdf(student_paper_path)
            answer_key_text = self.pdf_service.extract_text_from_pdf(answer_key_path)
            
            # Extract answers from both texts
            student_answers = self.gemini_service.extract_answers_from_text("\n".join(student_text))
            correct_answers = self.gemini_service.extract_answers_from_text("\n".join(answer_key_text))
            
            # Prepare answer pairs for evaluation
            answer_pairs = [
                {
                    "student_answer": student_answers.get(q_num, ""),
                    "correct_answer": answer
                }
                for q_num, answer in correct_answers.items()
            ]
            
            # Create scoring rubric (you might want to make this configurable)
            scoring_rubric = {
                q_num: 10 for q_num in correct_answers.keys()
            }
            
            # Evaluate answers
            evaluation_results = self.gemini_service.batch_evaluate_answers(
                answer_pairs,
                scoring_rubric
            )
            
            # Create a mapping of answers to their page numbers
            answer_page_map = {}
            doc = fitz.open(student_paper_path)
            try:
                for q_num, answer in student_answers.items():
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        if page.search_for(answer):
                            answer_page_map[answer] = page_num
                            break
            finally:
                doc.close()
            
            # Prepare corrections for marking
            corrections = []
            for q_num, score, feedback in evaluation_results:
                student_ans = student_answers.get(q_num, "")
                if student_ans:  # Only mark if we found an answer
                    page_num = answer_page_map.get(student_ans, 0)  # Default to first page if not found
                    corrections.append((
                        page_num,
                        student_ans,
                        feedback,
                        score >= (scoring_rubric[q_num] * 0.8)  # Consider correct if score >= 80%
                    ))
            
            # Generate marked PDF
            output_filename = f"marked_{Path(student_paper_path).name}"
            if not output_filename.endswith('.pdf'):
                output_filename += '.pdf'
                
            marked_pdf_path = self.pdf_service.create_marked_pdf(
                student_paper_path,
                corrections,
                output_filename
            )
            
            # Generate report
            report_filename = f"report_{Path(student_paper_path).name}"
            if not report_filename.endswith('.pdf'):
                report_filename += '.pdf'
                
            report_path = self.pdf_service.generate_report(
                student_name,
                evaluation_results,
                report_filename
            )
            
            return marked_pdf_path, report_path
            
        except Exception as e:
            import traceback
            print(f"Error processing submission: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Error processing submission: {str(e)}")
    
    def get_output_paths(self, original_filename: str) -> Tuple[Path, Path]:
        """Get the expected output paths for a submission."""
        marked_pdf = Path("static/output") / f"marked_{original_filename}"
        report_pdf = Path("static/output") / f"report_{original_filename}.pdf"
        return marked_pdf, report_pdf 