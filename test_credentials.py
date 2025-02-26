import os
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel

def test_gcp_connection():
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize Vertex AI
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION")
        
        vertexai.init(
            project=project_id,
            location=location
        )
        
        # Try to access Gemini model
        model = GenerativeModel("gemini-pro")
        
        print("✅ Successfully connected to GCP!")
        print(f"Project ID: {project_id}")
        print(f"Location: {location}")
        print(f"Credentials path: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        print("✅ Successfully accessed Gemini model!")
        
        # Test a simple prediction
        response = model.generate_content("Say hello!")
        print("\n✅ Model response:", response.text)
        
    except Exception as e:
        print("❌ Error occurred:")
        print(str(e))

if __name__ == "__main__":
    test_gcp_connection() 