# AI Grader

An AI-powered grading system that uses Google's Gemini model to automatically grade student answer papers by comparing them with answer keys.

## Features

- Upload and process PDF answer papers and answer keys
- AI-powered answer evaluation using Google's Gemini model
- Automatic text extraction and answer identification
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
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Set up Google Cloud credentials:
   - Create a project in Google Cloud Console
   - Enable the Gemini API
   - Create a service account and download the JSON key file
   - Set the environment variable:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/credentials.json"
     ```
   - On Windows:
     ```powershell
     $env:GOOGLE_APPLICATION_CREDENTIALS="path/to/your/credentials.json"
     ```

## Usage

1. Start the Streamlit application:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to the URL shown in the terminal (usually http://localhost:8501)

3. Use the application:
   - Enter the student's name
   - Upload the student's answer paper (PDF)
   - Upload the answer key (PDF)
   - Click "Grade Submission"
   - Download the marked PDF and grading report

### Output Format

The marked PDF will include:
- Original answer text with feedback placed immediately after each answer
- Proper spacing and line breaks for readability
- Color-coded feedback (green for correct answers, red for incorrect)
- Clear separation between answers and feedback
- No overlapping text or formatting issues

## Project Structure

```
ai-grader/
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── app/
│   └── services/
│       ├── gemini_service.py   # Gemini AI integration
│       ├── pdf_service.py      # PDF processing and formatting
│       └── grading_service.py  # Grading coordination
├── static/
│   └── output/            # Generated PDFs and reports
└── uploads/               # Temporary storage for uploads
```

## Configuration

The application uses the following environment variables:
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google Cloud service account key file
- `GOOGLE_CLOUD_PROJECT`: (Optional) Google Cloud project ID
- `GOOGLE_CLOUD_LOCATION`: (Optional) Google Cloud region (default: us-central1)

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 