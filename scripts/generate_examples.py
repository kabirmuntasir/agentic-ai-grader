from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

def create_answer_key():
    example_dir = Path("examples")
    example_dir.mkdir(exist_ok=True)
    
    c = canvas.Canvas(str(example_dir / "answer_key.pdf"), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, 10*inch, "Example Answer Key")
    
    c.setFont("Helvetica", 12)
    y = 9*inch
    questions = [
        ("1. What is the capital of France?", "Paris"),
        ("2. What is 2 + 2?", "4"),
        ("3. Who wrote Romeo and Juliet?", "William Shakespeare"),
        ("4. What is the chemical symbol for gold?", "Au"),
        ("5. What is the largest planet in our solar system?", "Jupiter")
    ]
    
    for question, answer in questions:
        y -= 0.5*inch
        c.drawString(1*inch, y, question)
        y -= 0.3*inch
        c.drawString(1.5*inch, y, f"Answer: {answer}")
        y -= 0.3*inch
    
    c.save()
    print("Generated answer key PDF")

def create_student_answer():
    example_dir = Path("examples")
    example_dir.mkdir(exist_ok=True)
    
    c = canvas.Canvas(str(example_dir / "john_doe.pdf"), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, 10*inch, "Student: John Doe")
    
    c.setFont("Helvetica", 12)
    y = 9*inch
    answers = [
        ("1. What is the capital of France?", "Paris"),
        ("2. What is 2 + 2?", "4"),
        ("3. Who wrote Romeo and Juliet?", "William Shakespear"),  # intentional misspelling
        ("4. What is the chemical symbol for gold?", "Au"),
        ("5. What is the largest planet in our solar system?", "Saturn")  # incorrect answer
    ]
    
    for question, answer in answers:
        y -= 0.5*inch
        c.drawString(1*inch, y, question)
        y -= 0.3*inch
        c.drawString(1.5*inch, y, f"Answer: {answer}")
        y -= 0.3*inch
    
    c.save()
    print("Generated student answer PDF")

if __name__ == "__main__":
    create_answer_key()
    create_student_answer() 