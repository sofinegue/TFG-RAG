import os
from docling.document import Document

def process_document(path):
	ext = os.path.splitext(path)[1].lower()
	if ext == '.json':
		doc = Document.from_json(path)
	elif ext == '.txt':
		doc = Document.from_txt(path)
	elif ext == '.pdf':
		doc = Document.from_pdf(path)
	else:
		raise ValueError(f"Unsupported file type: {ext}")
	# Divide en chunks usando docling
	chunks = doc.chunk()
	return chunks

# Ejemplo de uso con un documento de cada carpeta
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
	for doc_path in docs:
		try:
			chunks = process_document(doc_path)
			print(f"Procesado {doc_path}: {len(chunks)} chunks")
			print(f"Detalle de chunks de {doc_path}: {chunks}")
		except Exception as e:
			print(f"Error procesando {doc_path}: {e}")

    # # data/eu/en/inter-agree_2001.pdf
	# eu_doc_en = os.path.join("data", "eu", "en", "inter-agree_2001.pdf")
	# eu_doc_es = os.path.join("data", "eu", "es", "inter-agree_2001.pdf")
	# eu_doc_fr = os.path.join("data", "eu", "fr", "inter-agree_2001.pdf")
	# # data/cvs/en/cv_001.json
	# cvs_doc_en = os.path.join("data", "cvs", "en", "cv_001.json")
	# cvs_doc_es = os.path.join("data", "cvs", "es", "cv_001.json")
	# # data/wikipedia/en/json/Abbaye de Créteil.json
	# wiki_doc_en_json = os.path.join("data", "wikipedia", "en", "json", "Abbaye de Créteil.json")
	# wiki_doc_en_txt = os.path.join("data", "wikipedia", "en", "txt", "Abbaye de Créteil.txt")
	# wiki_doc_es_json = os.path.join("data", "wikipedia", "es", "json", "Autor.json")
	# wiki_doc_es_txt = os.path.join("data", "wikipedia", "es", "txt", "Autor.txt")