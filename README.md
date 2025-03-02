# AI Grader Pro

An intelligent, AI-powered grading system that leverages Google's Gemini model to automatically grade student answer papers by comparing them with answer keys. The system employs a multi-agent architecture where specialized AI agents handle different aspects of the grading process.

## Key Features

- **Intelligent Document Analysis**: Automatically analyzes PDF documents to identify questions and answer regions
- **AI-Powered Grading**: Uses Google's Gemini model to evaluate student answers against an answer key
- **Smart Feedback Placement**: Places feedback directly on the student's paper with appropriate formatting and color-coding
- **Quality Control**: Automatically verifies output quality and makes improvements if needed
- **Detailed Reports**: Generates comprehensive grading reports with scores and personalized feedback
- **Modern UI**: Clean, intuitive Streamlit interface with real-time grading progress display
- **Example Files**: Includes sample student answers and answer keys for testing

## Technical Architecture

### Multi-Agent Design

The system is built on a multi-agent architecture where specialized AI agents work together:

1. **Document Analyzer Agent**: Analyzes PDF layout to identify questions and answer regions
2. **Grading Agent**: Evaluates student answers against the answer key
3. **PDF Formatting Agent**: Places feedback appropriately on the student's paper
4. **Quality Control Agent**: Verifies output quality and suggests improvements

### Grading Process Flow

1. **Document Analysis**: Examines the structure of both the answer paper and answer key
2. **Answer Extraction**: Extracts individual answers from the student's paper
3. **Grading**: Evaluates each answer against the answer key using the Gemini model
4. **Feedback Generation**: Generates detailed feedback for each answer
5. **PDF Formatting**: Places feedback in the appropriate locations in the document
6. **Quality Control**: Verifies the output to ensure feedback is properly placed and readable
7. **Report Generation**: Creates a summary report with overall scores and comments

## Setup and Installation

### Prerequisites

- Python 3.8 or higher
- Google Cloud Platform account with Gemini API access
- Google Cloud credentials configured

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-grader.git
cd ai-grader
```

2. Create a virtual environment and activate it:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Set up Google Cloud credentials:
   - Create a project in Google Cloud Console
   - Enable the Gemini API
   - Create a service account and download the JSON key file
   - Place the credentials file in the `credentials` directory
   - Create a `.env` file with the following variables:
     ```
     GOOGLE_APPLICATION_CREDENTIALS=credentials/your-credentials-file.json
     GOOGLE_CLOUD_PROJECT=your-project-id
     GOOGLE_CLOUD_LOCATION=us-central1
     ```

### Docker Support

The application includes Docker support for containerized deployment:

```bash
docker build -t ai-grader .
docker run -p 8501:8501 ai-grader
```

## Usage Guide

1. Start the Streamlit application:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to the URL shown in the terminal (usually http://localhost:8501)

3. Use the application:
   - Enter the student's name
   - Upload the student's answer paper (PDF) or use the provided example
   - Upload the answer key (PDF) or use the provided example
   - Click "Grade Paper"
   - View the marked PDF and download the results (marked PDF and report)

## Project Structure

```
ai-grader/
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker configuration
├── .env                    # Environment variables (create from template)
├── app/
│   ├── agents/
│   │   ├── document_analyzer.py   # Document layout analysis
│   │   ├── grading_agent.py       # Answer evaluation
│   │   ├── pdf_formatter.py       # PDF feedback placement
│   │   └── quality_control.py     # Output verification
│   └── services/
│       ├── agentic_grading_service.py  # Coordinates the grading process
│       ├── gemini_service.py           # Gemini AI integration
├── examples/               # Example files for testing
├── static/
│   └── output/             # Generated PDFs and reports
├── uploads/                # Temporary storage for uploads
└── credentials/            # Google Cloud credentials (not included in repo)
```

## Environment Configuration

The application uses the following environment variables:
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google Cloud service account key file
- `GOOGLE_CLOUD_PROJECT`: Google Cloud project ID
- `GOOGLE_CLOUD_LOCATION`: Google Cloud region (default: us-central1)

## Testing

You can test your Google Cloud credentials setup by running:
```bash
python test_credentials.py
```

This will verify that your credentials are correctly configured and that you can access the Gemini model.

## Future Enhancements

- Support for additional file formats beyond PDF
- Integration with learning management systems (LMS)
- Batch processing of multiple submissions
- Enhanced analytics and reporting capabilities
- Customizable grading rubrics
- Support for additional languages

## License

This project is licensed under the MIT License - see the LICENSE file for details. 