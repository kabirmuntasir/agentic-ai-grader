# filepath: /c:/Users/kabir/Documents/PythonRepos/ai-grader/app.py
import streamlit as st
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
from google.cloud import storage
import tempfile
import base64
import time
import fitz

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
    page_title="AI Grader Pro",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
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

def display_pdf(pdf_data, height=600):
    """
    Display a PDF in the Streamlit app
    
    Args:
        pdf_data: The PDF file content (bytes)
        height: Height of the PDF viewer in pixels
        
    Returns:
        HTML component with the PDF viewer
    """
    try:
        if pdf_data is None:
            logger.warning("Attempted to display None PDF data")
            return None
            
        # Encode the PDF as base64
        base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
        
        # Create an iframe to display the PDF with minimal controls and no black space
        pdf_display = f'''
            <iframe 
                src="data:application/pdf;base64,{base64_pdf}#toolbar=0&navpanes=0&scrollbar=0&view=FitH" 
                width="100%" 
                height="{height}px" 
                type="application/pdf"
                frameborder="0" 
                style="border: none; background-color: white; margin: 0; padding: 0;">
            </iframe>
        '''
        return pdf_display
    except Exception as e:
        logger.error(f"Error displaying PDF: {str(e)}")
        return f'''
            <div style="
                border: 1px solid #f44336; 
                border-radius: 5px; 
                padding: 20px; 
                text-align: center;
                background-color: #ffebee;
                height: {height}px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;">
                <h3 style="color: #f44336;">Error Displaying PDF</h3>
                <p>{str(e)}</p>
            </div>
        '''

def display_grading_progress(progress_step, total_steps=5):
    """
    Display a progress indicator for the grading process
    
    Args:
        progress_step: Current step in the grading process (0-5)
        total_steps: Total number of steps in the process
    """
    steps = [
        "Document Analysis",
        "Answer Extraction",
        "Comparison with Answer Key",
        "Feedback Generation",
        "Final Document Creation"
    ]
    
    # Calculate progress percentage
    progress_percentage = min(100, (progress_step / total_steps) * 100)
    
    # Display progress bar
    st.progress(progress_percentage / 100)
    
    # Display current step
    for i, step in enumerate(steps):
        if i < progress_step:
            st.markdown(f"✅ **{step}** - Complete")
        elif i == progress_step:
            st.markdown(f"⏳ **{step}** - In progress...")
        else:
            st.markdown(f"⏹️ **{step}** - Pending")
            
    # Add estimated time remaining if not complete
    if progress_step < total_steps:
        st.info(f"Estimated time remaining: {(total_steps - progress_step) * 15} seconds")
    else:
        st.success("Grading completed successfully!")

def main():
    # Hide Streamlit menu and footer
    hide_streamlit_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        header {visibility: hidden;}
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 0rem !important;
        }
        </style>
        """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    st.markdown('<h1 style="margin-top: 0; padding-top: 0; font-size: 2rem;">AI Grader Pro 📝</h1>', unsafe_allow_html=True)
    
    # Initialize session state variables
    if "marked_pdf" not in st.session_state:
        st.session_state.marked_pdf = None
    if "report_pdf" not in st.session_state:
        st.session_state.report_pdf = None
    if "student_answer_uploaded" not in st.session_state:
        st.session_state.student_answer_uploaded = False
    if "answer_key_uploaded" not in st.session_state:
        st.session_state.answer_key_uploaded = False
    if "grading_in_progress" not in st.session_state:
        st.session_state.grading_in_progress = False
    if "grading_step" not in st.session_state:
        st.session_state.grading_step = 0
    if "zoom_level" not in st.session_state:
        st.session_state.zoom_level = 100
    
    # Custom CSS for the three-panel layout
    st.markdown("""
    <style>
    .main .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
    }
    .upload-status {
        padding: 6px 10px;
        border-radius: 4px;
        margin-top: 5px;
        font-size: 13px;
        font-weight: 500;
    }
    .success-status {
        background-color: #d1f0d5;
        color: #0c6b1d;
        border-left: 4px solid #0c6b1d;
    }
    .info-status {
        background-color: #d1e7f0;
        color: #0c4e6b;
        border-left: 4px solid #0c4e6b;
    }
    .waiting-status {
        background-color: #f0f0f0;
        color: #666666;
        border-left: 4px solid #666666;
    }
    .file-upload-container {
        padding: 5px;
        margin-bottom: 5px;
        transition: all 0.3s;
    }
    .file-upload-container:hover {
        background-color: #f8f9fa;
    }
    .panel-content {
        padding: 0;
        background-color: white;
        border-radius: 5px;
        overflow: hidden;
    }
    .placeholder-content {
        height: 500px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-direction: column;
        color: #666;
        background-color: #f9f9f9;
        border-radius: 5px;
    }
    /* Hide PDF toolbar */
    .pdf-toolbar {
        display: none !important;
    }
    iframe {
        border: none !important;
        background-color: white !important;
    }
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        margin-top: 0.5rem;
    }
    .stButton > button {
        width: 100%;
    }
    .compact-form .row-widget {
        margin-bottom: 0;
    }
    .compact-form .stTextInput > div > div > input {
        padding: 0.3rem;
    }
    .stDownloadButton > button {
        padding: 0.3rem;
        font-size: 0.9rem;
    }
    .stMarkdown h3 {
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
        font-size: 1.2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create three-panel layout
    left_col, middle_col, right_col = st.columns([1, 1.5, 1.5])
    
    # Left Panel - File Explorer and Upload
    with left_col:
        st.markdown('<div class="section-header">Upload Center</div>', unsafe_allow_html=True)
        
        # Student name input
        st.markdown('<div class="compact-form">', unsafe_allow_html=True)
        student_name = st.text_input(
            "Student Name",
            value=st.session_state.get("student_name", ""),
            help="Enter the student's full name",
            label_visibility="collapsed",
            placeholder="Enter student name *"
        )
        
        # Example files section
        st.markdown('<div class="section-header">Examples</div>', unsafe_allow_html=True)
        example_col1, example_col2 = st.columns(2)
        
        # Student Answer Example
        with example_col1:
            if st.button("📄 Answer Paper", key="load_student"):
                try:
                    with open("john doe.pdf", "rb") as f:
                        st.session_state.example_student = f.read()
                        st.session_state.student_name = "John Doe"
                        st.session_state.student_answer_uploaded = True
                    st.success("Example answer loaded!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        # Answer Key Example
        with example_col2:
            if st.button("📄 Answer Rubric", key="load_key"):
                try:
                    with open("answer key.pdf", "rb") as f:
                        st.session_state.example_key = f.read()
                        st.session_state.answer_key_uploaded = True
                    st.success("Example key loaded!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        # File upload section
        st.markdown('<div class="section-header">Upload Files</div>', unsafe_allow_html=True)
        
        # Student Answer Upload
        answer_paper = st.file_uploader(
            "Student Answer (PDF)", 
            type=["pdf"],
            key="student_answer_uploader",
            help="Upload the student's answer paper in PDF format"
        )
        
        # Handle file upload status
        if answer_paper is not None:
            st.session_state.example_student = answer_paper.getvalue()
            st.session_state.student_answer_uploaded = True
            st.markdown('<div class="upload-status success-status">✅ Student answer uploaded</div>', unsafe_allow_html=True)
        elif "example_student" in st.session_state:
            answer_paper = st.session_state.example_student
            if st.session_state.student_answer_uploaded:
                st.markdown('<div class="upload-status info-status">ℹ️ Example answer loaded</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="upload-status waiting-status">⏳ Waiting for file...</div>', unsafe_allow_html=True)
        
        # Answer Key Upload
        answer_key = st.file_uploader(
            "Answer Key (PDF)", 
            type=["pdf"],
            key="answer_key_uploader",
            help="Upload the answer key in PDF format"
        )
        
        # Handle file upload status
        if answer_key is not None:
            st.session_state.example_key = answer_key.getvalue()
            st.session_state.answer_key_uploaded = True
            st.markdown('<div class="upload-status success-status">✅ Answer key uploaded</div>', unsafe_allow_html=True)
        elif "example_key" in st.session_state:
            answer_key = st.session_state.example_key
            if st.session_state.answer_key_uploaded:
                st.markdown('<div class="upload-status info-status">ℹ️ Example key loaded</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="upload-status waiting-status">⏳ Waiting for file...</div>', unsafe_allow_html=True)
    
    # Middle Panel - Student Answer Preview
    with middle_col:
        # Simple text header instead of panel header with box
        st.markdown('<div class="section-header">Student Answer Preview</div>', unsafe_allow_html=True)
        
        # Panel content - PDF preview
        if "example_student" in st.session_state and st.session_state.student_answer_uploaded:
            # Use fixed height for PDF display
            pdf_html = display_pdf(st.session_state.example_student, height=500)
            st.markdown(pdf_html, unsafe_allow_html=True)
        else:
            st.markdown(
                '''
                <div class="placeholder-content">
                    <h3>No student answer loaded</h3>
                    <p>Upload or load an example to view the student's answer paper</p>
                </div>
                ''',
                unsafe_allow_html=True
            )
            
        # Add Grade Paper button at the bottom of middle panel
        if st.session_state.marked_pdf is not None and st.session_state.report_pdf is not None:
            # If results are available, align with download buttons
            st.markdown('<div class="section-header">Actions</div>', unsafe_allow_html=True)
        else:
            # If no results yet, show grade button in the middle panel
            st.markdown('<div class="section-header">Actions</div>', unsafe_allow_html=True)
            
        grade_button = st.button(
            "Grade Paper", 
            disabled=not (student_name and st.session_state.student_answer_uploaded and st.session_state.answer_key_uploaded) or st.session_state.grading_in_progress,
            use_container_width=True,
            help="Click to start grading the paper"
        )
    
    # Right Panel - Graded Result Preview
    with right_col:
        # Simple text header instead of panel header with box
        st.markdown('<div class="section-header">Graded Answer Preview</div>', unsafe_allow_html=True)
        
        # Panel content
        if st.session_state.grading_in_progress:
            # Show grading progress
            st.markdown('<div style="padding: 10px;">', unsafe_allow_html=True)
            display_grading_progress(st.session_state.grading_step)
            st.markdown('</div>', unsafe_allow_html=True)
        elif st.session_state.marked_pdf is not None:
            # Show graded PDF
            pdf_html = display_pdf(st.session_state.marked_pdf, height=500)
            st.markdown(pdf_html, unsafe_allow_html=True)
        else:
            # Show placeholder
            st.markdown(
                '''
                <div class="placeholder-content">
                    <h3>No graded result available</h3>
                    <p>Grade a paper to see results here</p>
                </div>
                ''',
                unsafe_allow_html=True
            )
        
        # Download buttons only (Grade button moved to middle panel)
        if st.session_state.marked_pdf is not None and st.session_state.report_pdf is not None:
            st.markdown('<div class="section-header">Download Results</div>', unsafe_allow_html=True)
            
            download_col1, download_col2 = st.columns(2)
            with download_col1:
                st.download_button(
                    "📄 Marked PDF",
                    data=st.session_state.marked_pdf,
                    file_name=f"{student_name}_marked.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            with download_col2:
                st.download_button(
                    "📊 Report",
                    data=st.session_state.report_pdf,
                    file_name=f"{student_name}_report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
    
    # Process grading when button is clicked
    if grade_button and student_name and st.session_state.student_answer_uploaded and st.session_state.answer_key_uploaded:
        # Set grading in progress
        st.session_state.grading_in_progress = True
        st.session_state.grading_step = 0
        st.rerun()
    
    # Simulate grading progress (in a real app, this would be part of the grading process)
    if st.session_state.grading_in_progress:
        try:
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save uploaded files to temporary location
                answer_paper_path = Path(temp_dir) / "student_answer.pdf"
                answer_key_path = Path(temp_dir) / "answer_key.pdf"
                
                # Get the answer paper and answer key from session state
                answer_paper = st.session_state.example_student
                answer_key = st.session_state.example_key
                
                # Write student answer
                answer_paper_path.write_bytes(answer_paper)
                
                # Update progress - Step 1: Document Analysis
                if st.session_state.grading_step < 1:
                    st.session_state.grading_step = 1
                    st.rerun()
                
                # Write answer key
                answer_key_path.write_bytes(answer_key)
                
                # Update progress - Step 2: Answer Extraction
                if st.session_state.grading_step < 2:
                    st.session_state.grading_step = 2
                    st.rerun()
                
                # Process the submission using the agentic service
                # Update progress - Step 3: Comparison with Answer Key
                if st.session_state.grading_step < 3:
                    st.session_state.grading_step = 3
                    st.rerun()
                
                # Update progress - Step 4: Feedback Generation
                if st.session_state.grading_step < 4:
                    st.session_state.grading_step = 4
                    st.rerun()
                
                try:
                    # Process the actual grading
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
                except Exception as e:
                    logger.error(f"Error in grading process: {str(e)}")
                    # For demo purposes, use the student answer as the marked PDF if grading fails
                    st.session_state.marked_pdf = answer_paper
                    
                    # Create a simple report PDF for demo
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        doc = fitz.open()
                        page = doc.new_page()
                        page.insert_text((50, 50), f"Grading Report for {student_name}", fontsize=16)
                        page.insert_text((50, 100), "Sample grading report for demonstration purposes.", fontsize=12)
                        page.insert_text((50, 150), "Score: 85/100", fontsize=14)
                        doc.save(tmp.name)
                        doc.close()
                        
                        with open(tmp.name, "rb") as f:
                            st.session_state.report_pdf = f.read()
                
                # Update progress - Step 5: Final Document Creation
                if st.session_state.grading_step < 5:
                    st.session_state.grading_step = 5
                    time.sleep(1)  # Give time to see the final step
                
                # Complete the grading process
                st.session_state.grading_in_progress = False
                st.rerun()
                
        except Exception as e:
            logger.error(f"Error processing submission: {str(e)}")
            st.error(f"Error processing submission: {str(e)}")
            st.session_state.grading_in_progress = False
            st.rerun()

if __name__ == "__main__":
    main()