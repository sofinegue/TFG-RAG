"""
Test SIMPLE del sistema de chunking
Procesa archivo local → Document Intelligence → Chunking → JSON local
SIN subir a Azure Blob Storage
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
import re

from config import config
from services.docintelligence_service import get_content_from_document
from document_ingestion.processchunks import (
    markdown_percentage,
    detect_title,
    detect_headers,
    generate_chunkid,
    get_most_common_locale
)


class SimpleChunkingTester:
    """Tester simple para chunking local"""
    
    def __init__(self):
        self.output_dir = Path("test_output")
        self.output_dir.mkdir(exist_ok=True)
        
    async def test_chunking(self, file_path: str, get_formulas: bool = False):
        """
        Test simple: archivo local → Document Intelligence → chunking → JSON
        
        Args:
            file_path: Ruta al archivo local
            get_formulas: Si extraer fórmulas matemáticas
        """
        print("\n" + "="*70)
        print("TEST SIMPLE DE CHUNKING")
        print("="*70)
        
        # 1. Validar archivo
        if not os.path.exists(file_path):
            print(f"Error: Archivo no encontrado: {file_path}")
            return
        
        file_name = os.path.basename(file_path)
        print(f"\nArchivo: {file_name}")
        
        # 2. Leer archivo
        print("\n[1/3] Leyendo archivo...")
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        
        print(f"Archivo leído: {len(file_bytes):,} bytes")
        
        # 3. Document Intelligence
        print("\n[2/3] Procesando con Document Intelligence...")
        try:
            result = await get_content_from_document(
                file_download=file_bytes,
                SessionId="test_local",
                Call_id="test_local",
                boolformulas=get_formulas
            )
            
            content = result.content
            print(f"Contenido extraído: {len(content):,} caracteres")
            
            # Guardar contenido raw
            raw_file = self.output_dir / f"{file_name}_raw.txt"
            # with open(raw_file, 'w', encoding='utf-8') as f:
            #     f.write(content)
            print(f"Contenido guardado: {raw_file}")
            
        except Exception as e:
            print(f"Error en Document Intelligence: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 4. Chunking
        print("\n[3/3] Aplicando chunking...")
        try:
            chunks = markdown_percentage(
                content=content,
                chunk_size=2000,
                chunk_overlap_percentage=0.1,
                min_tokens=1000,
                max_tokens=3000
            )
            
            print(f"Chunks generados: {len(chunks)}")
            
        except Exception as e:
            print(f"Error en chunking: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 5. Procesar chunks
        print("\nProcesando chunks...")
        processed_chunks = []
        
        # Detectar idioma
        try:
            top_language = get_most_common_locale(result) if hasattr(result, 'languages') else "es"
        except:
            top_language = "es"
        
        for index, chunk in enumerate(chunks, 1):
            # Detectar título y secciones
            title = detect_title(chunk)
            sections = []
            for level in range(1, 6):
                headers = detect_headers(chunk, level)
                sections.extend(headers)
            
            # Detectar páginas
            pages = re.findall(r'PG(\d+)', chunk)
            page_range = f"{pages[0]}-{pages[-1]}" if pages else "1"
            
            # Limpiar contenido
            clean_content = re.sub(r'PG\d+', '', chunk).strip()
            
            # Generar chunk ID
            chunk_id = generate_chunkid(
                doctitle=file_name,
                content=clean_content,
                title=title,
                page=page_range
            )
            
            # Estructura del chunk
            chunk_data = {
                "chunk_id": chunk_id,
                "n_chunk": index,
                "doc_title": file_name,
                "title": title,
                "sections": sections,
                "content": clean_content,
                "content_length": len(clean_content),
                "pages": page_range,
                "top_language": top_language,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "get_formulas": get_formulas
                }
            }
            
            processed_chunks.append(chunk_data)
            
            title_preview = title[:40] if title else "Sin título"
            print(f"  Chunk {index}/{len(chunks)}: {len(clean_content):,} chars - {title_preview}")
        
        # 6. Guardar chunks en JSON
        print("\nGuardando resultados...")
        
        # Primer chunk
        if processed_chunks:
            first_chunk_file = self.output_dir / f"{file_name}_chunk_001.json"
            with open(first_chunk_file, 'w', encoding='utf-8') as f:
                json.dump(processed_chunks[0], f, indent=2, ensure_ascii=False)
            print(f"Primer chunk: {first_chunk_file}")
        
        # Todos los chunks
        all_chunks_file = self.output_dir / f"{file_name}_all_chunks.json"
        with open(all_chunks_file, 'w', encoding='utf-8') as f:
            json.dump({
                "total_chunks": len(processed_chunks),
                "file_name": file_name,
                "created_at": datetime.now().isoformat(),
                "chunks": processed_chunks
            }, f, indent=2, ensure_ascii=False)
        print(f"Todos los chunks: {all_chunks_file}")
        
        # Resumen
        print("\n" + "="*70)
        print("RESUMEN")
        print("="*70)
        print(f"Archivo: {file_name}")
        print(f"Tamaño: {len(file_bytes):,} bytes")
        print(f"Contenido extraído: {len(content):,} caracteres")
        print(f"Chunks generados: {len(chunks)}")
        print(f"Idioma: {top_language}")
        print(f"\nArchivos generados:")
        print(f"  - {raw_file}")
        print(f"  - {first_chunk_file}")
        print(f"  - {all_chunks_file}")
        print("="*70)
        
        return processed_chunks


async def main():
    """Función principal"""
    
    print("\n" + "="*70)
    print("TEST CHUNKING LOCAL - RAG MODULAR")
    print("="*70)
    
    # Input
    test_file = input("\nRuta del archivo (PDF/DOCX/PPTX): ").strip()
    
    if not test_file:
        print("\nError: No se proporcionó archivo")
        return
    
    get_formulas = input("Extraer fórmulas matemáticas? (s/N): ").strip().lower() == 's'
    
    # Ejecutar test
    tester = SimpleChunkingTester()
    
    try:
        chunks = await tester.test_chunking(test_file, get_formulas)
        
        if chunks:
            print("\nTest completado exitosamente")
            print(f"Resultados en: test_output/")
        else:
            print("\nTest falló")
            
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())