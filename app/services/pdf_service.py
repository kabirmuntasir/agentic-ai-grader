import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Tuple
import os

class PDFService:
    def __init__(self):
        self.output_dir = Path("static/output")
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def extract_text_from_pdf(self, pdf_path: Path) -> List[str]:
        """Extract text from PDF file page by page."""
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page in doc:
                text = page.get_text()
                text_content.append(text)
                
            doc.close()
            return text_content
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")

    def create_marked_pdf(
        self,
        original_pdf_path: Path,
        corrections: List[Tuple[int, str, str, bool]],  # (page_num, text, comment, is_correct)
        output_filename: str
    ) -> Path:
        """Create a new PDF with markings and comments."""
        doc = None
        try:
            # Ensure the output directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # Open the original PDF
            doc = fitz.open(str(original_pdf_path))
            
            if len(doc) == 0:
                raise Exception("PDF document is empty")
            
            # Process each correction
            for page_num, text, comment, is_correct in corrections:
                if page_num >= len(doc):
                    continue
                    
                page = doc[page_num]
                
                # Clean up text for search
                search_text = text.strip()
                
                # Try to find the complete answer
                instances = page.search_for(search_text)
                if not instances:
                    # Try word-by-word search for longer answers
                    words = search_text.split()
                    word_instances = []
                    for word in words:
                        if len(word) > 3:  # Only search for meaningful words
                            found = page.search_for(word)
                            if found:
                                word_instances.extend(found)
                    
                    if word_instances:
                        # Combine word instances
                        combined_rect = fitz.Rect(
                            min(r.x0 for r in word_instances),
                            min(r.y0 for r in word_instances),
                            max(r.x1 for r in word_instances),
                            max(r.y1 for r in word_instances)
                        )
                        instances = [combined_rect]
                
                if instances:
                    # Use the instance with the largest width
                    inst = max(instances, key=lambda r: r.width)
                    
                    # Get page dimensions
                    page_width = page.rect.width
                    
                    # Find the exact end of the answer text
                    text_end = inst.x1
                    
                    # Add feedback text
                    font_size = 11
                    color = (1, 0, 0) if not is_correct else (0, 0.7, 0)
                    
                    # Calculate available width for feedback
                    available_width = page_width - text_end - 10  # 10 points margin
                    
                    # Calculate how many characters can fit in the available width
                    chars_per_line = int(available_width / (font_size * 0.5))  # Approximate width per char
                    
                    # Add feedback text
                    feedback_x = text_end + 15  # Increased gap to 15 points after answer text
                    feedback_y = inst.y0  # Same height as answer
                    
                    # If feedback is too long for available space, move to next line
                    if len(comment) > chars_per_line:
                        feedback_y = inst.y1 + 5  # Move below answer with 5 point gap
                        feedback_x = 50  # Fixed left margin for wrapped text
                        chars_per_line = int((page_width - 60) / (font_size * 0.5))  # Recalculate for full width minus margins
                    
                    # Add feedback text with line breaks if needed
                    words = comment.split()
                    current_line = []
                    current_length = 0
                    
                    for word in words:
                        if current_length + len(word) + 1 <= chars_per_line:
                            current_line.append(word)
                            current_length += len(word) + 1
                        else:
                            # Add current line
                            if current_line:
                                page.insert_text(
                                    (feedback_x, feedback_y),
                                    " ".join(current_line),
                                    fontsize=font_size,
                                    color=color
                                )
                                feedback_y += font_size + 2  # Move to next line
                                feedback_x = 50  # Reset to left margin for wrapped lines
                                current_line = [word]
                                current_length = len(word)
                    
                    # Add remaining words
                    if current_line:
                        page.insert_text(
                            (feedback_x, feedback_y),
                            " ".join(current_line),
                            fontsize=font_size,
                            color=color
                        )
            
            # Save the marked PDF
            output_path = self.output_dir / output_filename
            doc.save(str(output_path))
            
            return output_path
            
        except Exception as e:
            import traceback
            print(f"Error creating marked PDF: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Error creating marked PDF: {str(e)}")
            
        finally:
            if doc:
                doc.close()

    def generate_report(
        self,
        student_name: str,
        marks: List[Tuple[int, int, str]],  # (question_num, score, feedback)
        output_filename: str
    ) -> Path:
        """Generate a PDF report with marks and feedback."""
        try:
            doc = fitz.open()
            page = doc.new_page()
            
            # Add title
            y = 50
            page.insert_text((50, y), "Grading Report", fontsize=16)
            
            # Add student name
            y += 30
            page.insert_text((50, y), f"Student Name: {student_name}", fontsize=12)
            
            # Add marks table
            y += 30
            page.insert_text((50, y), "Question-wise Marks:", fontsize=12)
            
            y += 20
            total_score = 0
            for q_num, score, feedback in marks:
                y += 20
                page.insert_text((50, y), f"Question {q_num}: {score} marks")
                y += 15
                page.insert_text((70, y), f"Feedback: {feedback}")
                total_score += score
            
            # Add total score
            y += 40
            page.insert_text((50, y), f"Total Score: {total_score}", fontsize=14)
            
            # Save the report
            output_path = self.output_dir / output_filename
            doc.save(output_path)
            doc.close()
            
            return output_path
        except Exception as e:
            raise Exception(f"Error generating report: {str(e)}") 