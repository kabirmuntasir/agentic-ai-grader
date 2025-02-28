import logging
import os
try:
    import fitz  # PyMuPDF
except ImportError:
    from PyMuPDF import fitz
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.tools import tool
from .document_analyzer import LayoutAnalysisResult
from app.services.gemini_service import GeminiService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FormattingResult:
    """Results of PDF formatting"""
    marked_pdf_path: Path
    feedback_locations: List[Dict]
    success: bool

@dataclass
class FeedbackPlacement:
    """Details about where and how to place feedback"""
    page_num: int
    position: Tuple[float, float]  # (x, y)
    width: float
    text: str
    color: Tuple[float, float, float]
    is_multiline: bool

class PDFFormattingAgent:
    def __init__(self):
        # Initialize Gemini Service
        self.gemini_service = GeminiService()
        
        # Define tools for the agent
        tools = [
            Tool(
                name="analyze_layout",
                func=self._analyze_layout,
                description="Analyzes the layout of a PDF document. Input: pdf_path (string)"
            ),
            Tool(
                name="extract_text",
                func=self._extract_text,
                description="Extracts text from specific regions of a PDF. Input: dict with pdf_path (string), page_num (int), bounds (tuple of 4 floats)"
            )
        ]
        
        # Create the agent with updated parameters
        prompt = self._create_prompt()
        agent = create_react_agent(
            llm=self.gemini_service.model,
            tools=tools,
            prompt=prompt
        )
        
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True
        )
    
    def create_marked_pdf(
        self,
        original_pdf_path: Path,
        layout_analysis: LayoutAnalysisResult,
        feedback_data: List[Dict],
        output_path: Path,
        improvements: Dict = None
    ) -> Path:
        """
        Create a marked PDF with intelligently placed feedback.
        """
        try:
            # Open the original PDF
            doc = fitz.open(str(original_pdf_path))
            
            # Create a new PDF with larger dimensions to accommodate feedback
            new_doc = fitz.open()
            
            # Process each page
            for page_num in range(len(doc)):
                # Get original page
                old_page = doc[page_num]
                
                # Create new page with extra width for feedback
                new_page = new_doc.new_page(
                    width=old_page.rect.width * 1.4,  # 40% extra width for feedback
                    height=old_page.rect.height
                )
                
                # Calculate the target rectangle for the scaled content
                # Scale up by 10% and add padding
                scale = 1.1
                padding = 20
                target_rect = fitz.Rect(
                    padding,  # left
                    padding,  # top
                    old_page.rect.width * scale + padding,  # right
                    old_page.rect.height * scale + padding   # bottom
                )
                
                # Show the original page in the target rectangle
                new_page.show_pdf_page(
                    target_rect,  # target rectangle (this will handle scaling)
                    doc,          # source PDF
                    page_num      # source page number
                )
                
                # Get all questions on this page
                page_questions = [q for q in layout_analysis.question_regions 
                                if q.get("page") == page_num]
                
                # Calculate margin area start position
                margin_x = old_page.rect.width * scale + padding + 30  # Start of margin area
                margin_y = padding + 20  # Top padding in margin
                margin_width = (old_page.rect.width * 1.4) - margin_x - padding  # Available width in margin
                
                # Process each question on this page
                for question_info in page_questions:
                    question_num = question_info.get("question_num")
                    
                    # Find the corresponding feedback
                    feedback = next(
                        (f for f in feedback_data if f["question_num"] == question_num),
                        None
                    )
                    
                    if not feedback:
                        continue
                    
                    # Find the answer region
                    answer_info = self._find_answer_region(
                        question_info,
                        layout_analysis.answer_regions
                    )
                    
                    if not answer_info:
                        continue
                    
                    # Scale and shift the answer region coordinates
                    bbox = answer_info["bbox"]
                    answer_rect = fitz.Rect(
                        bbox[0] * scale + padding,
                        bbox[1] * scale + padding,
                        bbox[2] * scale + padding,
                        bbox[3] * scale + padding
                    )
                    
                    # Add visual indicators
                    # Add a colored box around the answer
                    highlight_color = (1, 0.9, 0.9) if not feedback["is_correct"] else (0.9, 1, 0.9)
                    new_page.draw_rect(
                        answer_rect,
                        color=highlight_color,
                        fill=highlight_color,
                        stroke_opacity=0.3,
                        fill_opacity=0.3
                    )
                    
                    # Add border
                    border_color = (1, 0, 0) if not feedback["is_correct"] else (0, 0.7, 0)
                    new_page.draw_rect(
                        answer_rect,
                        color=border_color,
                        width=2.0,
                        stroke_opacity=0.8
                    )
                    
                    # Place feedback text in margin
                    feedback_text = f"[Q{question_num}] {feedback['feedback']}"
                    
                    # Calculate text dimensions and position
                    font_size = 11
                    char_width = font_size * 0.5
                    line_height = font_size + 4
                    
                    # Split text into lines based on available width
                    words = feedback_text.split()
                    lines = []
                    current_line = []
                    current_width = 0
                    
                    for word in words:
                        word_width = len(word) * char_width
                        if current_width + word_width <= margin_width:
                            current_line.append(word)
                            current_width += word_width + char_width  # Add space width
                        else:
                            if current_line:
                                lines.append(" ".join(current_line))
                            current_line = [word]
                            current_width = word_width
                    
                    if current_line:
                        lines.append(" ".join(current_line))
                    
                    # Draw white background for feedback text
                    max_line_width = max(len(line) * char_width for line in lines)
                    text_rect = fitz.Rect(
                        margin_x - 4,
                        margin_y - 4,
                        margin_x + max_line_width + 8,
                        margin_y + (len(lines) * line_height) + 4
                    )
                    
                    # Draw white background
                    new_page.draw_rect(
                        text_rect,
                        color=(1, 1, 1),
                        fill=(1, 1, 1),
                        stroke_opacity=0.9,
                        fill_opacity=0.9
                    )
                    
                    # Draw border around feedback
                    new_page.draw_rect(
                        text_rect,
                        color=border_color,
                        width=1.0
                    )
                    
                    # Add feedback text lines
                    for i, line in enumerate(lines):
                        new_page.insert_text(
                            (margin_x, margin_y + (i * line_height) + font_size),  # Adjust y for baseline
                            line,
                            fontsize=font_size,
                            color=border_color
                        )
                    
                    # Update margin_y for next feedback block
                    margin_y = text_rect.y1 + 10  # Add spacing between feedback blocks
            
            # Save the new PDF
            new_doc.save(str(output_path))
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating marked PDF: {str(e)}")
            raise
        finally:
            if 'doc' in locals():
                doc.close()
            if 'new_doc' in locals():
                new_doc.close()
    
    def _find_answer_region(
        self,
        question_info: Dict,
        answer_regions: List[Dict]
    ) -> Dict:
        """Find the answer region that follows a question."""
        question_num = question_info.get("question_num")
        
        # First try to find answer with matching question number
        matching_answers = [
            a for a in answer_regions
            if a.get("question_num") == question_num
        ]
        
        if matching_answers:
            return matching_answers[0]
        
        # Fallback: try to find answer by position
        question_page = question_info["page"]
        question_bbox = question_info["bbox"]
        
        # Look for answers on the same page after the question
        same_page_answers = [
            a for a in answer_regions
            if (a["page"] == question_page and
                a["bbox"][1] > question_bbox[1] and  # Below the question
                a["bbox"][1] < question_bbox[3] + 100)  # Not too far below
        ]
        
        if same_page_answers:
            return min(same_page_answers, key=lambda a: a["bbox"][1])
        
        return None
    
    def _plan_feedback_placement(
        self,
        feedback_text: str,
        question_info: Dict,
        answer_info: Dict,
        layout: LayoutAnalysisResult,
        is_correct: bool
    ) -> FeedbackPlacement:
        """Plan the optimal placement for feedback text."""
        try:
            # Calculate text dimensions
            text_dims = self._calculate_text_dimensions(feedback_text)
            
            # Get page dimensions from layout info
            page_info = next(
                (p for p in layout.text_blocks if p["page"] == answer_info["page"]),
                None
            )
            
            # If no page info found in text blocks, get dimensions from the answer's page
            if not page_info:
                # Find any region on the same page to get dimensions
                same_page_regions = [
                    r for r in layout.question_regions + layout.answer_regions
                    if r["page"] == answer_info["page"]
                ]
                if same_page_regions:
                    # Use the maximum bounds of existing regions plus margin
                    page_dims = {
                        "width": max(r["bbox"][2] for r in same_page_regions) + 100,
                        "height": max(r["bbox"][3] for r in same_page_regions) + 100
                    }
                else:
                    # Use default A4 dimensions if no regions found
                    page_dims = {
                        "width": 595,  # A4 width in points
                        "height": 842  # A4 height in points
                    }
            else:
                # Use the bounding box of text blocks to determine page dimensions
                page_dims = {
                    "width": max(b["bbox"][2] for b in layout.text_blocks if b["page"] == answer_info["page"]) + 50,
                    "height": max(b["bbox"][3] for b in layout.text_blocks if b["page"] == answer_info["page"]) + 50
                }
            
            # Try positions in order of preference:
            # 1. Right of answer
            # 2. Below answer
            # 3. Next available space
            
            # 1. Try right of answer
            answer_bbox = answer_info["bbox"]
            x = answer_bbox[2] + 30  # Gap after answer
            y = answer_bbox[1]
            
            # Check if we have enough space on the right
            available_width = page_dims["width"] - x - 50
            
            if text_dims["width"] <= available_width:
                # Check for overlaps at this position
                test_rect = (x - 5, y - 5, x + text_dims["width"] + 5, y + text_dims["height"] + 5)
                if not self._has_overlap(test_rect, layout, answer_info["page"]):
                    return FeedbackPlacement(
                        page_num=answer_info["page"],
                        position=(x, y),
                        width=available_width,
                        text=feedback_text,
                        color=(0, 0.7, 0) if is_correct else (1, 0, 0),
                        is_multiline=False
                    )
            
            # 2. Try below answer
            x = answer_bbox[0]  # Align with answer start
            y = answer_bbox[3] + 15  # Gap below answer
            available_width = page_dims["width"] - x - 50
            
            # Check for overlaps and adjust position if needed
            test_rect = (x - 5, y - 5, x + available_width + 5, y + text_dims["height"] * 2 + 5)
            while self._has_overlap(test_rect, layout, answer_info["page"]):
                y += text_dims["height"] + 10  # Move down until we find free space
                if y > page_dims["height"] - 50:  # Too close to bottom
                    # 3. Find next available space
                    x, y = self._find_next_available_space(
                        text_dims,
                        layout,
                        answer_info["page"],
                        page_dims
                    )
                    break
                test_rect = (x - 5, y - 5, x + available_width + 5, y + text_dims["height"] * 2 + 5)
            
            return FeedbackPlacement(
                page_num=answer_info["page"],
                position=(x, y),
                width=available_width,
                text=feedback_text,
                color=(0, 0.7, 0) if is_correct else (1, 0, 0),
                is_multiline=True
            )
            
        except Exception as e:
            logger.error(f"Error planning feedback placement: {str(e)}")
            return None

    def _has_overlap(
        self,
        rect: Tuple[float, float, float, float],
        layout: LayoutAnalysisResult,
        page_num: int
    ) -> bool:
        """Check if a rectangle overlaps with any existing content."""
        # Check overlap with questions
        for q in layout.question_regions:
            if q["page"] == page_num and self._rectangles_overlap(rect, q["bbox"]):
                return True
        
        # Check overlap with answers
        for a in layout.answer_regions:
            if a["page"] == page_num and self._rectangles_overlap(rect, a["bbox"]):
                return True
        
        # Check overlap with other text blocks
        for block in layout.text_blocks:
            if block["page"] == page_num and self._rectangles_overlap(rect, block["bbox"]):
                return True
        
        return False

    def _find_next_available_space(
        self,
        text_dims: Dict,
        layout: LayoutAnalysisResult,
        page_num: int,
        page_info: Dict
    ) -> Tuple[float, float]:
        """Find the next available space for feedback text."""
        # Start from top of page with proper margin
        x = 50  # Left margin
        y = 50  # Top margin
        width = page_info["width"] - 100  # Account for margins
        
        while y < page_info["height"] - 50:
            test_rect = (x - 5, y - 5, x + width + 5, y + text_dims["height"] + 5)
            if not self._has_overlap(test_rect, layout, page_num):
                return x, y
            y += text_dims["height"] + 10
        
        # If we get here, we couldn't find space on this page
        # In practice, we should handle multi-page feedback, but for now:
        return 50, 50  # Return top-left with margins as last resort
    
    def _calculate_text_dimensions(
        self,
        text: str,
        font_size: int = 11
    ) -> Dict:
        """Calculate the dimensions needed for text placement."""
        # Approximate dimensions based on character count and font size
        char_width = font_size * 0.5  # Approximate width per character
        total_width = len(text) * char_width
        
        return {
            "width": total_width,
            "height": font_size + 2,  # Add padding
            "chars_per_line": int(total_width / char_width)
        }
    
    def _find_optimal_placement(
        self,
        text_dims: Dict,
        question_info: Dict,
        layout: LayoutAnalysisResult
    ) -> Dict:
        """Find the optimal placement for feedback text."""
        page_num = question_info["page"]
        question_bounds = question_info["bbox"]
        
        # Get the last word position of the answer
        doc = fitz.open()
        page = doc[page_num]
        answer_text = page.get_text("words", clip=question_bounds)
        if answer_text:
            last_word = answer_text[-1]
            x = last_word[0] + last_word[2]  # End of last word
        else:
            x = question_bounds[2]
        
        # Position feedback after a small gap
        x += 10  # 10 points gap after answer
        y = question_bounds[1]  # Same vertical position as answer start
        
        # Check if there's enough space on the same line
        available_width = page.rect.width - x - 30  # 30 points margin from right edge
        
        if text_dims["width"] <= available_width:
            # Can fit on same line
            return {
                "page_num": page_num,
                "position": (x, y),
                "width": available_width,
                "is_multiline": False
            }
        
        # If not enough space, move to next line with proper indentation
        y = question_bounds[3] + 5  # 5 points below answer
        x = question_bounds[0] + 20  # Indent from question start
        available_width = page.rect.width - x - 30
        
        # Check for overlapping text blocks
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block.get("type") == 0:  # Text block
                block_bbox = block["bbox"]
                # If block is below our answer and overlaps horizontally
                if (block_bbox[1] > question_bounds[3] and 
                    block_bbox[0] < x + available_width and
                    block_bbox[2] > x):
                    # Move below this block
                    y = max(y, block_bbox[3] + 5)
        
        return {
            "page_num": page_num,
            "position": (x, y),
            "width": available_width,
            "is_multiline": True
        }
    
    def _add_multiline_feedback(
        self,
        page,
        position: Tuple[float, float],
        width: float,
        text: str,
        color: Tuple[float, float, float]
    ):
        """Add multi-line feedback to the page."""
        font_size = 11
        line_spacing = font_size + 3  # Increased line spacing for better readability
        x, y = position
        
        # Calculate maximum characters per line based on font metrics
        char_width = font_size * 0.5  # Average character width
        max_chars_per_line = int(width / char_width)
        
        # Split text into words and distribute into lines
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            if current_length + word_length + 1 <= max_chars_per_line:
                current_line.append(word)
                current_length += word_length + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
        
        if current_line:
            lines.append(" ".join(current_line))
        
        # Add each line with proper spacing
        for i, line in enumerate(lines):
            # Add line
            page.insert_text(
                (x, y + i * line_spacing),
                line,
                fontsize=font_size,
                color=color
            )
            
            # Check if text was actually added (not clipped or overlapped)
            text_rect = fitz.Rect(
                x, y + i * line_spacing,
                x + len(line) * char_width,
                y + (i + 1) * line_spacing
            )
            
            # If text overlaps with existing content, try to move it
            blocks = page.get_text("dict", clip=text_rect)["blocks"]
            if len(blocks) > 1:  # More than our just-added text
                # Move remaining lines to next available space
                y = text_rect.y1 + 5  # Move below the overlap
                # Recalculate positions for remaining lines
                for j, remaining_line in enumerate(lines[i+1:]):
                    page.insert_text(
                        (x, y + j * line_spacing),
                        remaining_line,
                        fontsize=font_size,
                        color=color
                    )

    def _rectangles_overlap(
        self,
        rect1: Tuple[float, float, float, float],
        rect2: Tuple[float, float, float, float]
    ) -> bool:
        """Check if two rectangles overlap."""
        return not (
            rect1[2] < rect2[0] or  # rect1 is left of rect2
            rect1[0] > rect2[2] or  # rect1 is right of rect2
            rect1[3] < rect2[1] or  # rect1 is above rect2
            rect1[1] > rect2[3]     # rect1 is below rect2
        )

    def _analyze_layout(self, pdf_path: str) -> Dict:
        """Analyze the layout of a PDF document."""
        try:
            doc = fitz.open(pdf_path)
            layout_info = {
                "pages": [],
                "margins": [],
                "text_blocks": []
            }
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = page.get_text("dict")["blocks"]
                
                # Get page dimensions
                layout_info["pages"].append({
                    "number": page_num,
                    "width": page.rect.width,
                    "height": page.rect.height
                })
                
                # Calculate margins
                text_blocks = [b for b in blocks if b.get("type") == 0]
                if text_blocks:
                    left_margin = min(b["bbox"][0] for b in text_blocks)
                    right_margin = max(b["bbox"][2] for b in text_blocks)
                    top_margin = min(b["bbox"][1] for b in text_blocks)
                    bottom_margin = max(b["bbox"][3] for b in text_blocks)
                    
                    layout_info["margins"].append({
                        "page": page_num,
                        "left": left_margin,
                        "right": right_margin,
                        "top": top_margin,
                        "bottom": bottom_margin
                    })
                
                # Store text blocks
                layout_info["text_blocks"].extend([
                    {
                        "page": page_num,
                        "bbox": b["bbox"],
                        "text": b["text"],
                        "type": "text"
                    }
                    for b in text_blocks
                ])
            
            return layout_info
            
        except Exception as e:
            logger.error(f"Error analyzing PDF layout: {str(e)}")
            return {"error": str(e)}
        finally:
            if 'doc' in locals():
                doc.close()

    def _extract_text(self, input_data: Dict) -> Dict:
        """Extract text from specific regions of a PDF."""
        try:
            pdf_path = input_data["pdf_path"]
            page_num = input_data["page_num"]
            bounds = input_data["bounds"]
            
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            
            # Extract text from the specified region
            text = page.get_text("text", clip=bounds)
            
            return {
                "text": text,
                "region": {
                    "page": page_num,
                    "bounds": bounds
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return {"error": str(e)}
        finally:
            if 'doc' in locals():
                doc.close()

    def _create_prompt(self):
        """Create the prompt for the PDF formatting agent."""
        template = """You are a PDF formatting expert that specializes in placing feedback in documents.
        Your goal is to analyze document layouts and determine optimal positions for feedback text.
        
        You have access to the following tools:
        
        {tools}
        
        Use the following format:
        
        Question: the input question you must answer
        Thought: you should always think about what to do
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can repeat N times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question
        
        Begin!
        
        Question: {input}
        {agent_scratchpad}"""
        
        return PromptTemplate.from_template(template) 