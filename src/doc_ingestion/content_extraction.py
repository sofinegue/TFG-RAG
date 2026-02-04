import fitz  # PyMuPDF
import os

def extract_pdf_content(file_pdf):
    # Para PDFs
    doc = fitz.open(stream=file_pdf, filetype="pdf")
    
    result = {
        'content': '',
        'pages': [],
        'tables': [],
        'paragraphs': []
    }
    
    for page_num, page in enumerate(doc, 1):
        text = page.get_text()
        result['content'] += text
        result['pages'].append({
            'page_number': page_num,
            'content': text
        })
    
    return result

def extract_txt_or_json_content(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    result = {
        'content': content,
        'pages': [{
            'page_number': 1,
            'content': content
        }],
        'tables': [],
        'paragraphs': []
    }
    return result

def extract_content(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        with open(path, "rb") as f:
            return extract_pdf_content(f.read())
    elif ext in ['.txt', '.json']:
        return extract_txt_or_json_content(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def show_content(content):
    for key, elem in content.items():
        print(f"{key}: {elem}")

if __name__ == "__main__":
    docs = [
        # data/eu/en/inter-agree_2001.pdf
        os.path.join("data", "eu", "en", "inter-agree_2001.pdf"),
        os.path.join("data", "eu", "es", "inter-agree_2001.pdf"),
        os.path.join("data", "eu", "fr", "inter-agree_2001.pdf"),
        # data/cvs/en/cv_001.json
        os.path.join("data", "cvs", "en", "cv_001.json"),
        os.path.join("data", "cvs", "es", "cv_001.json"),
        # data/wikipedia/en/json/Abbaye de Créteil.json
        os.path.join("data", "wikipedia", "en", "json", "Abbaye de Créteil.json"),
        os.path.join("data", "wikipedia", "en", "txt", "Abbaye de Créteil.txt"),
        os.path.join("data", "wikipedia", "es", "json", "Autor.json"),
        os.path.join("data", "wikipedia", "es", "txt", "Autor.txt")
    ]
    for doc in docs:
        print(f"\nProcessing document: {doc}")
        content = extract_content(doc)
        show_content(content)