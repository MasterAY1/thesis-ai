import fitz  # PyMuPDF
import docx
import re
import os

def clean_text(text: str) -> str:
    """
    Cleans extracted text by normalizing spacing while PRESERVING paragraph breaks.
    Keeps double-newlines between paragraphs so heading detection works properly.
    """
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse 3+ newlines into 2 (preserve paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Replace multiple spaces with a single space (per line)
    text = re.sub(r'[^\S\n]+', ' ', text)
    # Strip leading and trailing whitespace
    return text.strip()

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts and cleans text from a PDF file using PyMuPDF.
    """
    extracted_text = []
    try:
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text:
                extracted_text.append(text)
        full_text = "\n".join(extracted_text)
        return clean_text(full_text)
    except Exception as e:
        print(f"Error extracting text from PDF {file_path}: {e}")
        return ""
    finally:
        if 'doc' in locals():
            doc.close()

def extract_text_from_docx(file_path: str) -> str:
    """
    Extracts and cleans text from a DOCX file.
    """
    try:
        doc = docx.Document(file_path)
        full_text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return clean_text(full_text)
    except Exception as e:
        print(f"Error extracting text from DOCX {file_path}: {e}")
        return ""

def extract_text(file_path: str) -> str:
    """
    Detects file type and extracts text accordingly.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    else:
        print(f"Unsupported file extension: {ext}")
        return ""
