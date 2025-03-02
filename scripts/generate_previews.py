from pathlib import Path
import fitz  # PyMuPDF

def generate_previews():
    example_dir = Path("examples")
    if not example_dir.exists():
        print("Examples directory not found!")
        return
        
    # Convert student answer PDF
    student_pdf = example_dir / "john_doe.pdf"
    if student_pdf.exists():
        doc = fitz.open(str(student_pdf))
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))  # scale down to 50%
        pix.save(str(example_dir / "john_doe_preview.png"))
        doc.close()
        print("Generated student answer preview")
        
    # Convert answer key PDF
    answer_key = example_dir / "answer_key.pdf"
    if answer_key.exists():
        doc = fitz.open(str(answer_key))
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))  # scale down to 50%
        pix.save(str(example_dir / "answer_key_preview.png"))
        doc.close()
        print("Generated answer key preview")

if __name__ == "__main__":
    generate_previews() 