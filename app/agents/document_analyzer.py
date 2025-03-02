import logging
import os
import re
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
class LayoutAnalysisResult:
    """Results of document layout analysis"""
    question_regions: List[Dict]
    answer_regions: List[Dict]
    text_blocks: List[Dict]
    confidence: float

class DocumentAnalyzerAgent:
    def __init__(self):
        # Initialize Gemini Service
        self.gemini_service = GeminiService()
        
        # Define tools for the agent
        tools = [
            Tool(
                name="analyze_layout",
                func=self._analyze_layout,
                description="Analyzes the layout of a PDF document to identify question and answer regions"
            ),
            Tool(
                name="extract_text",
                func=self._extract_text,
                description="Extracts text from specific regions of a PDF page"
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
        """Create the prompt for the document analyzer agent."""
        template = """You are a document analysis expert that identifies question and answer regions in PDFs.
        Your goal is to accurately locate and extract text from these regions.
        
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
    
    def analyze_layout(self, pdf_path: Path) -> LayoutAnalysisResult:
        """
        Analyze a PDF document to identify question and answer regions.
        Returns a LayoutAnalysisResult with the analysis.
        """
        try:
            # Convert Path to string for the agent
            pdf_path_str = str(pdf_path)
            
            # Run layout analysis
            result = self._analyze_layout(pdf_path_str)
            
            if "error" in result:
                raise Exception(result["error"])
            
            # Extract layout information
            layout_info = result.get("layout", [])
            
            # Separate questions, answers, and text blocks
            question_regions = []
            answer_regions = []
            text_blocks = []
            
            # First, identify questions and answers
            for region in layout_info:
                if region["type"] == "question":
                    question_regions.append(region)
                elif region["type"] == "answer":
                    answer_regions.append(region)
            
            # Then, get all text blocks from the document
            doc = fitz.open(pdf_path_str)
            try:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    blocks = page.get_text("dict")["blocks"]
                    
                    # Add all text blocks
                    for block in blocks:
                        if block.get("type") == 0:  # Text block
                            # Extract text from spans to ensure we have valid text
                            block_text = ""
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    if span.get("text"):
                                        block_text += span["text"] + " "
                            block_text = block_text.strip()
                            
                            if not block_text:  # Skip empty blocks
                                continue
                                
                            # Add all text blocks without checking for overlap
                            text_blocks.append({
                                "page": page_num,
                                "bbox": block["bbox"],
                                "text": block_text,
                                "type": "text"
                            })
                            
                            # Log the text block for debugging
                            logger.debug(f"Found text block on page {page_num + 1}: {block_text[:100]}...")
            finally:
                doc.close()
            
            # Sort questions by number
            question_regions.sort(key=lambda x: x["question_num"])
            
            # Log what we found
            logger.info(f"Processed layout analysis: {len(question_regions)} questions, {len(answer_regions)} answers, {len(text_blocks)} other text blocks")
            logger.info("Text blocks found:")
            for block in text_blocks:
                logger.info(f"Page {block['page'] + 1}: {block['text'][:100]}...")
            
            return LayoutAnalysisResult(
                question_regions=question_regions,
                answer_regions=answer_regions,
                text_blocks=text_blocks,
                confidence=result.get("confidence", 0.0)
            )
            
        except Exception as e:
            logger.error(f"Error in document analysis: {str(e)}")
            raise
    
    def _analyze_layout(self, pdf_path: str) -> Dict:
        """Tool function to analyze PDF layout."""
        try:
            doc = fitz.open(pdf_path)
            layout_info = []
            current_question = None
            current_question_bbox = None
            
            logger.info(f"Analyzing PDF: {pdf_path}")
            
            for page_num, page in enumerate(doc):
                logger.info(f"Processing page {page_num + 1}")
                
                # Get raw text with line information
                text_page = page.get_textpage()
                text_dict = text_page.extractDICT()
                
                # Log the raw text for debugging
                raw_text = page.get_text()
                logger.debug(f"Raw text from page {page_num + 1}:\n{raw_text}")
                
                for block in text_dict["blocks"]:
                    if block.get("type") == 0:  # Text block
                        # Get all lines in this block
                        lines = block.get("lines", [])
                        for line_idx, line in enumerate(lines):
                            # Get text from spans
                            text = " ".join(span["text"] for span in line.get("spans", []))
                            text = text.strip()
                            
                            logger.debug(f"Processing line: {text}")
                            
                            # Calculate bbox for this line
                            bbox = line["bbox"]
                            
                            # Check for various question patterns
                            patterns = [
                                r'^Question\s*(\d+)\s*:\s*(.+?)(?:\s*Answer:)?',  # Question X: [text]
                                r'^Q\.?\s*(\d+)\s*[:.]\s*(.+?)(?:\s*Answer:)?',   # Q.X: [text]
                                r'^(\d+)\s*[.)\]]\s*(.+?)(?:\s*Answer:)?',        # X. or X) [text]
                                r'^Question\s*(\d+)\s*[.)\]]\s*(.+?)(?:\s*Answer:)?'  # Question X. [text]
                            ]
                            
                            is_question = False
                            for pattern in patterns:
                                match = re.match(pattern, text, re.IGNORECASE)
                                if match:
                                    question_num = int(match.group(1))
                                    question_text = match.group(2).strip()
                                    
                                    logger.info(f"Found Question {question_num} on page {page_num + 1}")
                                    
                                    # Add question region
                                    layout_info.append({
                                        "page": page_num,
                                        "bbox": bbox,
                                        "text": question_text,
                                        "type": "question",
                                        "question_num": question_num
                                    })
                                    current_question = question_num
                                    current_question_bbox = bbox
                                    is_question = True
                                    break
                            
                            if not is_question and current_question:
                                # Check for explicit Answer pattern
                                answer_patterns = [
                                    r'^Answer\s*:\s*(.+)',
                                    r'^A\s*:\s*(.+)',
                                    r'^Ans\s*:\s*(.+)'
                                ]
                                
                                found_answer = False
                                for pattern in answer_patterns:
                                    answer_match = re.match(pattern, text, re.IGNORECASE)
                                    if answer_match:
                                        answer_text = answer_match.group(1).strip()
                                        logger.info(f"Found Answer for Question {current_question} on page {page_num + 1}")
                                        layout_info.append({
                                            "page": page_num,
                                            "bbox": bbox,
                                            "text": answer_text,
                                            "type": "answer",
                                            "question_num": current_question
                                        })
                                        found_answer = True
                                        break
                                
                                # If no explicit answer marker, check if this is answer text
                                # (text that follows a question and isn't another question)
                                if not found_answer and current_question_bbox and bbox[1] > current_question_bbox[3]:
                                    # Check this isn't the start of another question
                                    if not any(re.match(p, text, re.IGNORECASE) for p in patterns):
                                        logger.info(f"Found implied answer for Question {current_question} on page {page_num + 1}")
                                        layout_info.append({
                                            "page": page_num,
                                            "bbox": bbox,
                                            "text": text,
                                            "type": "answer",
                                            "question_num": current_question
                                        })
            
            # Sort layout info by page and vertical position
            layout_info.sort(key=lambda x: (x["page"], x["bbox"][1]))
            
            # Log summary
            questions_found = len([x for x in layout_info if x["type"] == "question"])
            answers_found = len([x for x in layout_info if x["type"] == "answer"])
            logger.info(f"Analysis complete. Found {questions_found} questions and {answers_found} answers.")
            
            if questions_found == 0:
                logger.error("No questions were detected in the document!")
                logger.error("This might be due to unexpected formatting or OCR issues.")
            
            if answers_found == 0:
                logger.warning("No answers were detected in the document!")
                logger.warning("This might be due to missing answer markers or unexpected formatting.")
            
            return {
                "layout": layout_info,
                "confidence": 0.9 if questions_found > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing PDF layout: {str(e)}")
            return {"error": str(e)}
        finally:
            if 'doc' in locals():
                doc.close()
    
    def _extract_text(self, params: Dict) -> str:
        """Tool function to extract text from specific regions."""
        try:
            pdf_path = params.get("pdf_path")
            regions = params.get("regions", [])
            
            if not pdf_path or not regions:
                return {"error": "Missing required parameters"}
            
            doc = fitz.open(pdf_path)
            extracted_text = []
            
            for region in regions:
                page_num = region.get("page", 0)
                bbox = region.get("bbox")
                
                if page_num < len(doc) and bbox:
                    page = doc[page_num]
                    text = page.get_text("text", clip=bbox)
                    extracted_text.append(text.strip())
            
            return {
                "text": "\n".join(extracted_text)
            }
            
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return {"error": str(e)}
        finally:
            if 'doc' in locals():
                doc.close()
    
    def _rectangles_overlap(
        self,
        rect1: tuple,
        rect2: tuple
    ) -> bool:
        """Check if two rectangles overlap."""
        return not (
            rect1[2] < rect2[0] or  # rect1 is left of rect2
            rect1[0] > rect2[2] or  # rect1 is right of rect2
            rect1[3] < rect2[1] or  # rect1 is above rect2
            rect1[1] > rect2[3]     # rect1 is below rect2
        ) 