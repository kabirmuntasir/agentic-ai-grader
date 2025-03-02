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
from langchain.tools import tool
from app.services.gemini_service import GeminiService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QCResult:
    """Results of quality control check"""
    is_approved: bool
    issues: List[str]
    improvements: Dict[str, any]

class QualityControlAgent:
    def __init__(self):
        # Initialize Gemini Service
        self.gemini_service = GeminiService()
        
        # Define tools for the agent
        tools = [
            Tool(
                name="verify_feedback_placement",
                func=self._verify_feedback_placement,
                description="Verifies the placement of feedback in a PDF. Input: pdf_path (string)"
            ),
            Tool(
                name="check_feedback_quality",
                func=self._check_feedback_quality,
                description="Checks the quality of feedback text. Input: list of feedback strings"
            )
        ]
        
        # Create the agent with updated parameters
        prompt = self._create_prompt()
        
        # Create the agent executor
        self.agent_executor = AgentExecutor(
            agent=create_react_agent(
                llm=self.gemini_service.model,
                tools=tools,
                prompt=prompt
            ),
            tools=tools,
            verbose=True
        )
    
    def _create_prompt(self):
        """Create the prompt for the quality control agent."""
        template = """You are a quality control expert that verifies PDF feedback placement and content.
        Your goal is to ensure feedback is properly placed and readable in the document.
        
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
    
    def _verify_feedback_placement(self, pdf_path: str) -> Dict:
        """Verify the placement of feedback in a PDF."""
        try:
            doc = fitz.open(pdf_path)
            issues = []
            
            for page_num, page in enumerate(doc):
                # Get all text blocks
                blocks = page.get_text("dict")["blocks"]
                
                # Check for overlapping text
                for i, block1 in enumerate(blocks):
                    if block1.get("type") != 0:  # Not a text block
                        continue
                        
                    rect1 = fitz.Rect(block1["bbox"])
                    
                    for block2 in blocks[i+1:]:
                        if block2.get("type") != 0:
                            continue
                            
                        rect2 = fitz.Rect(block2["bbox"])
                        
                        if rect1.intersects(rect2):
                            issues.append({
                                "type": "overlap",
                                "page": page_num,
                                "location": {
                                    "x": rect1.x0,
                                    "y": rect1.y0
                                }
                            })
            
            return {
                "has_issues": len(issues) > 0,
                "issues": issues
            }
            
        except Exception as e:
            logger.error(f"Error verifying feedback placement: {str(e)}")
            return {"error": str(e)}
        finally:
            if 'doc' in locals():
                doc.close()
    
    def _check_feedback_quality(self, feedback_list: List[str]) -> Dict:
        """Check the quality of feedback text."""
        try:
            # Create quality check prompt
            prompt = f"""
            Analyze the quality of these feedback comments:
            
            {feedback_list}
            
            Check for:
            1. Clarity and conciseness
            2. Constructive tone
            3. Actionable suggestions
            4. Professional language
            
            Return a JSON object with:
            {{"issues": [
                {{"text": "feedback text", "problem": "description", "suggestion": "improvement"}}
            ]}}
            """
            
            # Get analysis from LLM
            response = self.gemini_service.model.invoke(prompt)
            
            # Parse response
            import json
            result = json.loads(response.content)
            
            return {
                "has_issues": len(result["issues"]) > 0,
                "issues": result["issues"]
            }
            
        except Exception as e:
            logger.error(f"Error checking feedback quality: {str(e)}")
            return {"error": str(e)}
    
    def verify_output(
        self,
        marked_pdf_path: Path,
        original_feedback: List[Dict]
    ) -> QCResult:
        """
        Verify the quality of the marked PDF output.
        Returns QCResult with is_approved=False if any critical issues are found.
        """
        try:
            # Open the PDF
            doc = fitz.open(str(marked_pdf_path))
            
            all_issues = []
            all_improvements = {
                "feedback_adjustments": [],
                "layout_suggestions": []
            }
            
            # Track which feedback items were found
            feedback_found = {f["question_num"]: False for f in original_feedback}
            
            # Check each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # Check each feedback item
                for feedback in original_feedback:
                    q_num = feedback["question_num"]
                    feedback_text = f"[Q{q_num}]"
                    
                    # Check if feedback is present
                    if feedback_text in page_text:
                        feedback_found[q_num] = True
                        
                        # Verify feedback is readable
                        if not self._verify_feedback_readability(page, feedback_text):
                            all_issues.append(f"Feedback for Q{q_num} may not be readable")
                
                # Check for overlapping text
                blocks = page.get_text("dict")["blocks"]
                for i, block1 in enumerate(blocks):
                    if block1.get("type") != 0:  # Not a text block
                        continue
                    
                    rect1 = fitz.Rect(block1["bbox"])
                    for block2 in blocks[i+1:]:
                        if block2.get("type") != 0:
                            continue
                        
                        rect2 = fitz.Rect(block2["bbox"])
                        if rect1.intersects(rect2):
                            all_issues.append(f"Text overlap detected on page {page_num + 1}")
                
                # Check text visibility
                for block in blocks:
                    if block.get("type") == 0:  # Text block
                        bbox = block["bbox"]
                        if (bbox[0] < 0 or bbox[2] > page.rect.width or
                            bbox[1] < 0 or bbox[3] > page.rect.height):
                            all_issues.append(f"Text extends beyond page margins on page {page_num + 1}")
            
            # Check if all feedback was found
            missing_feedback = [
                q_num for q_num, found in feedback_found.items()
                if not found
            ]
            
            if missing_feedback:
                all_issues.append(f"Missing feedback for questions: {', '.join(map(str, missing_feedback))}")
            
            # Determine if output should be approved
            is_approved = len(all_issues) == 0
            
            if not is_approved:
                logger.error("Quality control failed:")
                for issue in all_issues:
                    logger.error(f"- {issue}")
            
            return QCResult(
                is_approved=is_approved,  # Only approve if no issues
                issues=all_issues,
                improvements=all_improvements
            )
            
        except Exception as e:
            logger.error(f"Error in quality control: {str(e)}")
            # If QC fails, DO NOT allow the output
            return QCResult(
                is_approved=False,  # Changed to False
                issues=[f"Quality control check failed: {str(e)}"],
                improvements={}
            )
        finally:
            if 'doc' in locals():
                doc.close()
    
    def _verify_feedback_readability(self, page, feedback_text: str) -> bool:
        """
        Verify that feedback text is readable (has proper contrast and isn't obscured).
        """
        try:
            # Get the text block containing the feedback
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    text = "".join(span["text"] for line in block.get("lines", []) for span in line.get("spans", []))
                    if feedback_text in text:
                        # Check if block has a background (should have white background)
                        rect = fitz.Rect(block["bbox"])
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
                        if pixmap.pixel(0, 0) != (255, 255, 255):  # Not white background
                            return False
                        return True
            return False
        except Exception as e:
            logger.error(f"Error checking feedback readability: {str(e)}")
            return False
    
    def _extract_page_content(self, page) -> Dict:
        """Extract structured content from a page."""
        return {
            "text": page.get_text("text"),
            "blocks": page.get_text("dict")["blocks"],
            "dimensions": (page.rect.width, page.rect.height)
        }
    
    def _is_feedback_on_page(self, feedback: Dict, page_content: Dict) -> bool:
        """Check if feedback appears on the given page."""
        return feedback["feedback"] in page_content["text"]
    
    def _parse_qc_result(self, result: str) -> Dict:
        """Parse the QC chain result."""
        try:
            # Clean up the result text
            cleaned_result = (
                result.strip()
                .split("```json")[-1]
                .split("```")[0]
                .strip()
            )
            
            import json
            return json.loads(cleaned_result)
            
        except Exception as e:
            logger.error(f"Error parsing QC result: {str(e)}")
            return {}
    
    def _check_feedback_placement(self, doc) -> List[str]:
        """Check feedback placement relative to answers."""
        issues = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            # Look for potential overlaps
            for i, block in enumerate(blocks):
                if block.get("type") == 0:  # Text block
                    bbox = block["bbox"]
                    
                    # Check for overlaps with other blocks
                    for other_block in blocks[i+1:]:
                        if other_block.get("type") == 0:
                            other_bbox = other_block["bbox"]
                            
                            if self._rectangles_overlap(bbox, other_bbox):
                                issues.append(
                                    f"Text overlap detected on page {page_num + 1}"
                                )
        
        return issues
    
    def _verify_text_visibility(self, doc) -> List[str]:
        """Verify all text is visible and not cut off."""
        issues = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    bbox = block["bbox"]
                    
                    # Check if text extends beyond page margins
                    if (bbox[0] < 0 or bbox[2] > page.rect.width or
                        bbox[1] < 0 or bbox[3] > page.rect.height):
                        issues.append(
                            f"Text extends beyond page margins on page {page_num + 1}"
                        )
        
        return issues
    
    def _analyze_spacing(self, doc) -> List[str]:
        """Analyze spacing between elements."""
        issues = []
        min_space = 2  # Minimum space between elements
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = sorted(
                page.get_text("dict")["blocks"],
                key=lambda x: (x["bbox"][1], x["bbox"][0])
            )
            
            for i in range(len(blocks) - 1):
                if blocks[i].get("type") == 0 and blocks[i+1].get("type") == 0:
                    space = blocks[i+1]["bbox"][1] - blocks[i]["bbox"][3]
                    if space < min_space:
                        issues.append(
                            f"Insufficient spacing between text blocks on page {page_num + 1}"
                        )
        
        return issues
    
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