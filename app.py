# filepath: /c:/Users/kabir/Documents/PythonRepos/ai-grader/app.py
import streamlit as st
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
from google.cloud import storage
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file if not in production
if not os.getenv("K_SERVICE"):  # Check if running in Cloud Run
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

sys.path.append(str(Path(__file__).resolve().parent / "app"))
from app.services.agentic_grading_service import AgenticGradingService

# Set page config
st.set_page_config(
    page_title="AI Grader",
    page_icon="📝",
    layout="centered"
)

# Ensure environment variables are set
if not os.getenv("GOOGLE_CLOUD_PROJECT"):
    st.error("GOOGLE_CLOUD_PROJECT environment variable is not set.")
    sys.exit(1)

# Initialize services
grading_service = AgenticGradingService()

# Initialize Google Cloud Storage if in production
if os.getenv("K_SERVICE"):
    storage_client = storage.Client()
    bucket_name = f"{os.getenv('GOOGLE_CLOUD_PROJECT')}-ai-grader"
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except Exception:
        bucket = storage_client.create_bucket(bucket_name)
else:
    # Create local directories in development
    UPLOAD_DIR = Path("uploads")
    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR = Path("static/output")
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def save_to_storage(file_data, filename, folder="output"):
    """Save file to appropriate storage (GCS in production, local in development)"""
    if os.getenv("K_SERVICE"):
        blob = bucket.blob(f"{folder}/{filename}")
        if isinstance(file_data, bytes):
            blob.upload_from_string(file_data)
        else:
            blob.upload_from_filename(file_data)
        return blob.public_url
    else:
        output_path = Path(f"static/{folder}/{filename}")
        if isinstance(file_data, bytes):
            output_path.write_bytes(file_data)
        else:
            from shutil import copy
            copy(file_data, output_path)
        return str(output_path)

def main():
    st.title("AI Grader 📝")
    st.write("Upload student answer papers and answer keys for automated grading using AI")
    
    # Initialize session state variables
    if "marked_pdf" not in st.session_state:
        st.session_state.marked_pdf = None
    if "report_pdf" not in st.session_state:
        st.session_state.report_pdf = None
    
    # Examples section
    st.sidebar.subheader("Examples")
    
    # Create two columns for the examples
    col1, col2 = st.sidebar.columns(2)
    
    # Student Answer Example
    with col1:
        st.markdown("📄 **Student Answer**")
        if st.button("Load Example Answer", key="load_student"):
            try:
                with open("john doe.pdf", "rb") as f:
                    st.session_state.example_student = f.read()
                    st.session_state.student_name = "John Doe"
                st.success("Student answer loaded!")
            except Exception as e:
                st.error(f"Error loading example: {str(e)}")
    
    # Answer Key Example
    with col2:
        st.markdown("📄 **Answer Key**")
        if st.button("Load Example Key", key="load_key"):
            try:
                with open("answer key.pdf", "rb") as f:
                    st.session_state.example_key = f.read()
                st.success("Answer key loaded!")
            except Exception as e:
                st.error(f"Error loading example: {str(e)}")
    
    # Main form
    with st.form("grading_form"):
        student_name = st.text_input(
            "Student Name",
            value=st.session_state.get("student_name", "")
        )
        
        # File uploads
        col1, col2 = st.columns(2)
        with col1:
            answer_paper = st.file_uploader(
                "Student Answer (PDF)", 
                type=["pdf"]
            )
            if "example_student" in st.session_state and not answer_paper:
                st.info("Example loaded")
                answer_paper = st.session_state.example_student
        
        with col2:
            answer_key = st.file_uploader(
                "Answer Key (PDF)", 
                type=["pdf"]
            )
            if "example_key" in st.session_state and not answer_key:
                st.info("Example loaded")
                answer_key = st.session_state.example_key
        
        submit = st.form_submit_button("Grade Submission")
        
    if submit and student_name and answer_paper and answer_key:
        with st.spinner("Processing submission..."):
            try:
                # Create temporary directory for processing
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Save uploaded files to temporary location
                    answer_paper_path = Path(temp_dir) / "student_answer.pdf"
                    answer_key_path = Path(temp_dir) / "answer_key.pdf"
                    
                    # Write student answer
                    if isinstance(answer_paper, bytes):
                        answer_paper_path.write_bytes(answer_paper)
                    else:
                        answer_paper_path.write_bytes(answer_paper.getvalue())
                    
                    # Write answer key
                    if isinstance(answer_key, bytes):
                        answer_key_path.write_bytes(answer_key)
                    else:
                        answer_key_path.write_bytes(answer_key.getvalue())
                    
                    # Process the submission using the agentic service
                    marked_pdf_path, report_path, quality_check_passed = grading_service.process_submission(
                        answer_paper_path,
                        answer_key_path,
                        student_name
                    )
                    
                    # Read the output files into memory
                    with open(marked_pdf_path, "rb") as f:
                        marked_pdf_data = f.read()
                    with open(report_path, "rb") as f:
                        report_data = f.read()
                    
                    # Store PDFs in session state
                    st.session_state.marked_pdf = marked_pdf_data
                    st.session_state.report_pdf = report_data
                    st.session_state.quality_check_passed = quality_check_passed
                    
                    # Show appropriate message
                    if quality_check_passed:
                        st.success("Grading completed successfully!")
                    else:
                        st.warning("Grading completed but some feedback may not be clearly visible. You can still download the PDFs to review the results.")
                    
            except Exception as e:
                logger.error(f"Error processing submission: {str(e)}")
                st.error(f"Error processing submission: {str(e)}")
    
    # Show download buttons if files exist in session state
    if st.session_state.marked_pdf and st.session_state.report_pdf:
        if not st.session_state.quality_check_passed:
            st.info("Note: The quality control check detected some issues with feedback placement. The feedback might overlap or be difficult to read in some places.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                "Download Marked PDF",
                data=st.session_state.marked_pdf,
                file_name=f"{student_name}_marked.pdf",
                mime="application/pdf"
            )
        
        with col2:
            st.download_button(
                "Download Report",
                data=st.session_state.report_pdf,
                file_name=f"{student_name}_report.pdf",
                mime="application/pdf"
            )

if __name__ == "__main__":
    main()