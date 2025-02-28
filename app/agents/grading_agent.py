import logging
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import tool
import json
import os
from app.services.gemini_service import GeminiService

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
    confidence: float

class GradingAgent:
    def __init__(self):
        # Initialize Gemini Service
        self.gemini_service = GeminiService()
        
        # Define tools for the agent
        tools = [
            Tool(
                name="evaluate_answer",
                func=self._evaluate_answer,
                description="Evaluates a student's answer against the correct answer. Input: dict with student_answer (string) and correct_answer (string)"
            ),
            Tool(
                name="extract_answers",
                func=self._extract_answers,
                description="Extracts answers from text. Input: dict with text (string) and question_numbers (list of ints)"
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
        """Create the prompt for the grading agent."""
        template = """You are an expert grader that evaluates student answers.
        Your goal is to provide accurate and constructive feedback on student responses.
        
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
    
    def _evaluate_answer(self, params: Dict) -> Dict:
        """Tool function to evaluate a student's answer."""
        try:
            student_answer = params.get("student_answer", "")
            correct_answer = params.get("correct_answer", "")
            max_score = params.get("max_score", 10)
            
            # Create evaluation prompt
            prompt = f"""
            Task: Evaluate the student's answer against the correct answer and provide a detailed score and feedback.
            
            Correct Answer:
            {correct_answer}
            
            Student's Answer:
            {student_answer}
            
            Maximum Score: {max_score}
            
            Evaluation Criteria:
            1. Content Accuracy (40%):
               - Key points match the correct answer
               - No major misconceptions or errors
            
            2. Completeness (30%):
               - All required elements are present
               - Sufficient detail provided
            
            3. Understanding (30%):
               - Demonstrates clear understanding of concepts
               - Uses appropriate terminology
            
            Return a JSON object with:
            {{
                "score": number (0-{max_score}),
                "feedback": "specific, constructive feedback explaining the score",
                "is_correct": boolean (true if score >= 80% of max)
            }}
            """
            
            # Get evaluation from LLM
            response = self.gemini_service.model.invoke(prompt)
            
            # Parse response and extract score, feedback, and correctness
            result = json.loads(response.content)
            
            # Ensure score is within bounds
            score = min(max(0, result["score"]), max_score)
            
            return {
                "score": score,
                "feedback": result["feedback"][:200],  # Limit feedback length but allow more detail
                "is_correct": score >= (max_score * 0.8)  # 80% threshold for correctness
            }
            
        except Exception as e:
            logger.error(f"Error evaluating answer: {str(e)}")
            return {"error": str(e)}
    
    def _extract_answers(self, params: Dict) -> Dict:
        """Tool function to extract answers from text."""
        try:
            text = params.get("text", "")
            question_numbers = params.get("question_numbers", [])
            
            # Create extraction prompt
            prompt = f"""
            Task: Extract answers from the following text and organize them by question number.
            
            Text Content:
            {text}
            
            Instructions:
            1. Look for answers that follow question numbers or question markers
            2. Include the complete answer text for each question
            3. Ignore question text, only extract answers
            4. If an answer spans multiple lines, include all lines
            5. If no clear answer is found for a question, skip it
            
            Return ONLY a JSON object in this exact format:
            {{"answers": {{"1": "answer1", "2": "answer2", ...}}}}
            """
            
            # Get extraction from LLM
            response = self.gemini_service.model.invoke(prompt)
            
            # Clean up the response text and handle potential JSON issues
            cleaned_response_text = (
                response.content
                .strip()
                .split("```json")[-1]  # Take the last part if multiple JSON blocks exist
                .split("```")[0]  # Take content between ``` markers
                .strip()
                .replace("'", '"')  # Replace single quotes with double quotes
                .replace('\n', ' ')  # Remove newlines
            )
            
            try:
                # Parse response and extract answers
                result = json.loads(cleaned_response_text)
                
                answers = {
                    int(k): v.strip()
                    for k, v in result["answers"].items()
                }
                
                # If question numbers were specified, filter to only those
                if question_numbers:
                    answers = {
                        q_num: answers[q_num]
                        for q_num in question_numbers
                        if q_num in answers
                    }
                
                return {"answers": answers}
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                logger.error(f"Attempted to parse: {cleaned_response_text}")
                return {"error": str(e)}
            
        except Exception as e:
            logger.error(f"Error extracting answers: {str(e)}")
            return {"error": str(e)}
    
    def grade_submission(
        self,
        student_answers: Dict[int, str],
        correct_answers: Dict[int, str],
        scoring_rubric: Dict[int, int] = None
    ) -> List[Dict]:
        """
        Grade a student's submission by comparing their answers to the correct answers.
        Returns a list of grading results.
        """
        try:
            results = []
            
            # Use default scoring if no rubric provided
            if not scoring_rubric:
                scoring_rubric = {q: 10 for q in correct_answers.keys()}
            
            # Grade each answer
            for question_num, correct_answer in correct_answers.items():
                student_answer = student_answers.get(question_num, "")
                max_score = scoring_rubric.get(question_num, 10)
                
                try:
                    # Create evaluation prompt
                    prompt = f"""
                    Task: Grade this student answer and provide feedback.
                    
                    Question {question_num}
                    
                    Correct Answer:
                    {correct_answer}
                    
                    Student Answer:
                    {student_answer}
                    
                    Maximum Score: {max_score}
                    
                    Evaluate based on:
                    1. Accuracy of content
                    2. Completeness of answer
                    3. Understanding shown
                    
                    Provide a VERY CONCISE feedback (max 100 characters).
                    
                    Return ONLY a JSON object in this exact format:
                    {{
                        "score": <number between 0 and {max_score}>,
                        "feedback": "<brief feedback>",
                        "is_correct": <true if score >= {max_score * 0.8}, false otherwise>
                    }}
                    """
                    
                    # Get evaluation from Gemini
                    response = self.gemini_service.model.invoke(prompt)
                    
                    # Clean up response and parse JSON
                    cleaned_response = (
                        response.content
                        .strip()
                        .split("```json")[-1]
                        .split("```")[0]
                        .strip()
                        .replace("'", '"')
                        .replace('\n', ' ')
                    )
                    
                    result = json.loads(cleaned_response)
                    
                    # Validate and clean up the result
                    score = min(max(int(result["score"]), 0), max_score)
                    feedback = result["feedback"].strip()[:100]
                    is_correct = score >= (max_score * 0.8)
                    
                    results.append({
                        "question_num": question_num,
                        "score": score,
                        "feedback": feedback,
                        "is_correct": is_correct
                    })
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON for question {question_num}: {str(e)}")
                    logger.error(f"Raw response: {response.content}")
                    # Add fallback result
                    results.append({
                        "question_num": question_num,
                        "score": 0,
                        "feedback": "Error processing response",
                        "is_correct": False
                    })
                except Exception as e:
                    logger.error(f"Error evaluating question {question_num}: {str(e)}")
                    results.append({
                        "question_num": question_num,
                        "score": 0,
                        "feedback": "Error during evaluation",
                        "is_correct": False
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in grading submission: {str(e)}")
            raise
    
    def _analyze_answer_quality(
        self,
        answer: str
    ) -> Dict:
        """Analyze the quality and completeness of an answer."""
        try:
            # Create a quality analysis prompt
            prompt = f"""
            Analyze the quality of this answer in terms of:
            1. Completeness
            2. Clarity
            3. Use of relevant terminology
            4. Structure
            
            Answer to analyze:
            {answer}
            
            Return a JSON object with:
            {{"completeness": float, "clarity": float, "terminology": float, "structure": float}}
            """
            
            # Get analysis from LLM
            response = self.gemini_service.model.invoke(prompt)
            
            # Parse and return the analysis
            cleaned_result = (
                response.content.strip()
                .split("```json")[-1]
                .split("```")[0]
                .strip()
            )
            
            return json.loads(cleaned_result)
            
        except Exception as e:
            logger.error(f"Error in answer quality analysis: {str(e)}")
            raise 