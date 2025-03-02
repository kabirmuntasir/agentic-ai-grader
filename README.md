# AI Grader Pro

An AI-powered grading system that uses Google's Gemini model to automatically grade student answer papers by comparing them with answer keys. The system employs an agentic approach with specialized AI agents for different aspects of the grading process.

## Features

- Upload and process PDF answer papers and answer keys
- AI-powered answer evaluation using Google's Gemini model
- Intelligent document analysis with automatic question and answer identification
- Multi-agent architecture for specialized processing:
  - Document analysis agent for layout understanding
  - Grading agent for answer evaluation
  - PDF formatting agent for feedback placement
  - Quality control agent for output verification
- Smart feedback placement:
  - Feedback appears immediately after each answer
  - Proper line breaks and spacing for readability
  - No overlapping between answers and feedback
  - Clear color-coding (green for correct, red for incorrect)
- Detailed grading reports with scores and comments
- Modern and user-friendly Streamlit interface

## Prerequisites

- Python 3.8 or higher
- Google Cloud Platform account with Gemini API access
- Google Cloud credentials configured

## Installation

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

## Usage

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
   - View the marked PDF and download the results

### Grading Process Flow

1. **Document Analysis**: The document analyzer agent examines the structure of both the answer paper and answer key to identify questions and answers.
2. **Answer Extraction**: The system extracts individual answers from the student's paper based on the layout analysis.
3. **Grading**: The grading agent evaluates each answer against the answer key using the Gemini model.
4. **Feedback Generation**: The system generates detailed feedback for each answer.
5. **PDF Formatting**: The PDF formatting agent places feedback in the appropriate locations in the document.
6. **Quality Control**: The quality control agent verifies the output to ensure feedback is properly placed and readable.
7. **Report Generation**: A summary report is generated with overall scores and comments.

## Project Structure

```
ai-grader/
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── app/
│   ├── agents/
│   │   ├── document_analyzer.py   # Document layout analysis
│   │   ├── grading_agent.py       # Answer evaluation
│   │   ├── pdf_formatter.py       # PDF feedback placement
│   │   └── quality_control.py     # Output verification
│   └── services/
│       ├── agentic_grading_service.py  # Coordinates the grading process
│       ├── gemini_service.py           # Gemini AI integration
│       ├── pdf_service.py              # PDF processing
│       └── grading_service.py          # Basic grading functionality
├── examples/               # Example files for testing
│   ├── student_answer.pdf
│   └── answer_key.pdf
├── static/
│   └── output/             # Generated PDFs and reports
└── uploads/                # Temporary storage for uploads
```

## Configuration

The application uses the following environment variables:
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google Cloud service account key file
- `GOOGLE_CLOUD_PROJECT`: Google Cloud project ID
- `GOOGLE_CLOUD_LOCATION`: Google Cloud region (default: us-central1)

## Testing Credentials

You can test your Google Cloud credentials setup by running:
```bash
python test_credentials.py
```

This will verify that your credentials are correctly configured and that you can access the Gemini model.

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 