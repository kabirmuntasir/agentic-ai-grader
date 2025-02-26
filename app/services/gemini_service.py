# filepath: /c:/Users/kabir/Documents/PythonRepos/ai-grader/app/services/gemini_service.py
import logging
from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel
from typing import List, Tuple, Dict
import json
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        # Initialize Vertex AI
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set.")
        
        vertexai.init(
            project=project_id,
            location=location
        )
        self.model = GenerativeModel("gemini-pro")
        
    def evaluate_answer(
        self,
        student_answer: str,
        correct_answer: str,
        max_score: int
    ) -> Tuple[int, str, bool]:
        """
        Evaluate a student's answer against the correct answer using Gemini model.
        Returns: (score, feedback, is_correct)
        """
        try:
            # Create the prompt for Gemini
            prompt = f"""
            Task: Evaluate the student's answer against the correct answer and provide a brief score and feedback.
            
            Correct Answer:
            {correct_answer}
            
            Student's Answer:
            {student_answer}
            
            Maximum Score: {max_score}
            
            Please evaluate based on:
            1. Accuracy of content
            2. Completeness of answer
            3. Understanding of concepts
            
            Provide a VERY CONCISE feedback (max 100 characters) focusing on the main point only.
            Return ONLY a JSON object in this exact format (no markdown, no formatting):
            {{"score": number, "feedback": "brief feedback with no special characters", "is_correct": boolean}}
            """
            
            # Log the prompt
            logger.info(f"Sending prompt to Gemini: {prompt}")
            
            # Get prediction
            response = self.model.generate_content(prompt)
            
            # Log the response
            logger.info(f"Received response from Gemini: {response.text}")
            
            # Clean up the response text and handle potential JSON issues
            cleaned_response_text = (
                response.text
                .strip()
                .split("```json")[-1]  # Take the last part if multiple JSON blocks exist
                .split("```")[0]  # Take content between ``` markers
                .strip()
                .replace("\n", " ")  # Replace newlines with spaces
                .replace("**", "")   # Remove markdown formatting
            )
            
            try:
                # Parse the response
                result = json.loads(cleaned_response_text)
                
                # Ensure the feedback is properly formatted and truncated
                result["feedback"] = (
                    result["feedback"]
                    .replace("\\n", " ")  # Replace newlines with spaces
                    .strip()
                )[:100]  # Limit to 100 characters
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                logger.error(f"Attempted to parse: {cleaned_response_text}")
                # Fallback response if JSON parsing fails
                return (
                    0,
                    "Error processing response. Please try again.",
                    False
                )
            
            return (
                result["score"],
                result["feedback"],
                result["is_correct"]
            )
            
        except Exception as e:
            logger.error(f"Error evaluating answer with Gemini: {str(e)}")
            logger.error(f"Response text: {response.text}")
            raise Exception(f"Error evaluating answer with Gemini: {str(e)}")
    
    def batch_evaluate_answers(
        self,
        answer_pairs: List[Dict[str, str]],
        scoring_rubric: Dict[int, int]  # question_num: max_score
    ) -> List[Tuple[int, int, str]]:
        """
        Evaluate multiple answers and return list of (question_num, score, feedback)
        """
        results = []
        
        for q_num, pair in enumerate(answer_pairs, 1):
            max_score = scoring_rubric.get(q_num, 10)  # Default max score is 10
            score, feedback, _ = self.evaluate_answer(
                pair["student_answer"],
                pair["correct_answer"],
                max_score
            )
            results.append((q_num, score, feedback))
        
        return results
    
    def extract_answers_from_text(
        self,
        text_content: str
    ) -> Dict[int, str]:
        """
        Extract answers from text content using Gemini's text understanding capabilities.
        Returns a dictionary of question numbers to answers.
        """
        try:
            # Create the prompt for Gemini
            prompt = f"""
            Task: Extract answers from the following text content and organize them by question number.
            
            Text Content:
            {text_content}
            
            Return ONLY the JSON output without any additional text or explanation:
            {{
                "answers": {{
                    "1": "answer for question 1",
                    "2": "answer for question 2",
                    ...
                }}
            }}
            """
            
            # Log the prompt
            logger.info(f"Sending prompt to Gemini: {prompt}")
            
            # Get prediction
            response = self.model.generate_content(prompt)
            
            # Log the response
            logger.info(f"Received response from Gemini: {response.text}")
            
            # Clean up the response text and handle potential JSON issues
            cleaned_response_text = (
                response.text
                .strip()
                .split("```json")[-1]  # Take the last part if multiple JSON blocks exist
                .split("```")[0]  # Take content between ``` markers
                .strip()
            )
            
            try:
                # Parse the response
                result = json.loads(cleaned_response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                logger.error(f"Attempted to parse: {cleaned_response_text}")
                # Return empty dict if parsing fails
                return {}
            
            return {
                int(k): v for k, v in result["answers"].items()
            }
            
        except Exception as e:
            logger.error(f"Error extracting answers with Gemini: {str(e)}")
            logger.error(f"Response text: {response.text}")
            raise Exception(f"Error extracting answers with Gemini: {str(e)}")