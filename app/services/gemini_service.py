# filepath: /c:/Users/kabir/Documents/PythonRepos/ai-grader/app/services/gemini_service.py
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
import json
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        
        # Initialize Langchain's Gemini model
        self.model = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True
        )
    
    def invoke(self, prompt: str) -> str:
        """
        Invoke the Gemini model through Langchain.
        """
        try:
            # Create a structured message to ensure JSON response
            structured_prompt = f"""
            {prompt}
            
            IMPORTANT: Your response must be valid JSON. Do not include any explanatory text.
            If the response includes JSON, wrap it in ```json``` markers.
            
            Example format:
            ```json
            {{"key": "value"}}
            ```
            
            ONLY return the JSON object, no other text or explanation.
            """
            
            response = self.model.invoke(structured_prompt)
            
            # Log raw response for debugging
            logger.debug(f"Raw response from Gemini: {response}")
            
            # Clean up the response text and handle potential JSON issues
            cleaned_response_text = (
                response.content
                .strip()
                .split("```json")[-1]  # Take the last part if multiple JSON blocks exist
                .split("```")[0]  # Take content between ``` markers
                .strip()
            )
            
            # Log cleaned response for debugging
            logger.debug(f"Cleaned response text: {cleaned_response_text}")
            
            # Validate JSON before returning
            try:
                json.loads(cleaned_response_text)  # Test if it's valid JSON
            except json.JSONDecodeError:
                # If not valid JSON, try to fix common issues
                fixed_text = cleaned_response_text.replace("'", '"')  # Replace single quotes with double quotes
                fixed_text = fixed_text.replace('\n', ' ')  # Remove newlines
                json.loads(fixed_text)  # Test again
                cleaned_response_text = fixed_text
            
            return response
            
        except Exception as e:
            logger.error(f"Error invoking Gemini model: {str(e)}")
            raise
    
    def evaluate_answer(
        self,
        student_answer: str,
        correct_answer: str,
        max_score: int
    ) -> tuple[int, str, bool]:
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
            response = self.invoke(prompt)
            
            # Log the response
            logger.info(f"Received response from Gemini: {response.content}")
            
            # Clean up the response text and handle potential JSON issues
            cleaned_response_text = (
                response.content
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
            raise
    
    def extract_answers_from_text(
        self,
        text_content: str
    ) -> dict[int, str]:
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
            response = self.invoke(prompt)
            
            # Log the response
            logger.info(f"Received response from Gemini: {response.content}")
            
            # Clean up the response text and handle potential JSON issues
            cleaned_response_text = (
                response.content
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
            raise