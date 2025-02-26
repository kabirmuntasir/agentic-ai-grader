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
from services.grading_service import GradingService

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
grading_service = GradingService()

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
    
    # Initialize session state for file downloads
    if 'marked_pdf' not in st.session_state:
        st.session_state.marked_pdf = None
    if 'report_pdf' not in st.session_state:
        st.session_state.report_pdf = None
    
    # Create form for file uploads
    with st.form("grading_form"):
        student_name = st.text_input("Student Name", key="student_name")
        answer_paper = st.file_uploader("Upload Student Answer Paper (PDF)", type=["pdf"], key="answer_paper")
        answer_key = st.file_uploader("Upload Answer Key (PDF)", type=["pdf"], key="answer_key")
        
        submit_button = st.form_submit_button("Grade Submission")
        
    if submit_button and student_name and answer_paper and answer_key:
        with st.spinner("Processing submission..."):
            try:
                # Save uploaded files to temporary location
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_answer_paper:
                    tmp_answer_paper.write(answer_paper.getvalue())
                    answer_paper_path = Path(tmp_answer_paper.name)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_answer_key:
                    tmp_answer_key.write(answer_key.getvalue())
                    answer_key_path = Path(tmp_answer_key.name)
                
                # Process the submission
                marked_pdf_path, report_path = grading_service.process_submission(
                    answer_paper_path,
                    answer_key_path,
                    student_name
                )
                
                # Save to appropriate storage
                marked_pdf_url = save_to_storage(marked_pdf_path, f"{student_name}_marked.pdf")
                report_url = save_to_storage(report_path, f"{student_name}_report.pdf")
                
                # Store URLs in session state
                st.session_state.marked_pdf = marked_pdf_url
                st.session_state.report_pdf = report_url
                
                # Show success message
                st.success("Grading completed successfully!")
                
                # Clean up temporary files
                os.unlink(answer_paper_path)
                os.unlink(answer_key_path)
                os.unlink(marked_pdf_path)
                os.unlink(report_path)
                
            except Exception as e:
                logger.error(f"Error processing submission: {str(e)}")
                st.error(f"Error processing submission: {str(e)}")
    
    # Show download buttons if files exist in session state
    if st.session_state.marked_pdf and st.session_state.report_pdf:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f'<a href="{st.session_state.marked_pdf}" target="_blank">Download Marked PDF</a>', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'<a href="{st.session_state.report_pdf}" target="_blank">Download Report</a>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()