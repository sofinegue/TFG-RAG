import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from jsonschema import validate, ValidationError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataValidator:
    """Valida archivos JSON contra esquemas predefinidos"""
    
    def __init__(self, schemas_dir: str = 'schemas'):
        self.schemas_dir = Path(schemas_dir)
        self.schemas = self._load_schemas()
    
    def _load_schemas(self) -> Dict[str, dict]:
        """Carga todos los esquemas disponibles"""
        schemas = {}
        
        if not self.schemas_dir.exists():
            logger.warning(f"Carpeta de esquemas no encontrada: {self.schemas_dir}")
            return schemas
        
        for schema_file in self.schemas_dir.glob('*.json'):
            schema_name = schema_file.stem
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schemas[schema_name] = json.load(f)
                # print(f"Esquema cargado: {schema_name}")
            except json.JSONDecodeError as e:
                logger.error(f"Error al cargar esquema {schema_name}: {e}")
        
        return schemas
    
    def validate_file(self, file_path: str, schema_name: str) -> Tuple[bool, List[str]]:
        """
        Valida un archivo JSON contra un esquema específico
        
        Args:
            file_path: Ruta del archivo JSON a validar
            schema_name: Nombre del esquema (sin .json)
        
        Returns:
            Tupla (es_válido, lista_de_errores)
        """
        errors = []
        file_path = Path(file_path)
        
        if not file_path.exists():
            return False, [f"Archivo no encontrado: {file_path}"]
        
        if schema_name not in self.schemas:
            return False, [f"Esquema no encontrado: {schema_name}"]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"JSON inválido: {e}"]
        
        schema = self.schemas[schema_name]
        
        try:
            validate(instance=data, schema=schema)
            return True, []
        except ValidationError as e:
            errors.append(f"Error de validación: {e.message}")
            errors.append(f"Ruta: {' -> '.join(str(p) for p in e.path)}")
            return False, errors
    
    def validate_directory(self, directory: str, schema_name: str, pattern: str = '*.json') -> Dict[str, Tuple[bool, List[str]]]:
        """
        Valida todos los archivos JSON en un directorio
        
        Args:
            directory: Ruta del directorio
            schema_name: Nombre del esquema a usar
            pattern: Patrón de archivos a validar (por defecto *.json)
        
        Returns:
            Diccionario {archivo: (es_válido, errores)}
        """
        results = {}
        dir_path = Path(directory)
        
        if not dir_path.exists():
            logger.error(f"Directorio no encontrado: {dir_path}")
            return results
        
        json_files = list(dir_path.glob(pattern))
        print(f"Validando {len(json_files)} archivos en {dir_path}")
        
        for json_file in json_files:
            is_valid, errors = self.validate_file(str(json_file), schema_name)
            results[str(json_file)] = (is_valid, errors)
        
        return results


def validate_cvs(validator: DataValidator, verbose: bool = False) -> Tuple[int, int]:
    """Valida todos los CVs generados (español e inglés)"""
    # print("VALIDANDO CVs")

    total_valid = 0
    total_invalid = 0
    
    # Validar CVs en español
    # print("[ES] Validando CVs en español...")
    results_es = validator.validate_directory('data/cvs/es', 'cv_schema', '*.json')
    total_valid += sum(1 for is_valid, _ in results_es.values() if is_valid)
    total_invalid += sum(1 for is_valid, _ in results_es.values() if not is_valid)
    
    # Validar CVs en inglés
    # print("[EN] Validando CVs en inglés...")
    results_en = validator.validate_directory('data/cvs/en', 'cv_schema', '*.json')
    total_valid += sum(1 for is_valid, _ in results_en.values() if is_valid)
    total_invalid += sum(1 for is_valid, _ in results_en.values() if not is_valid)
    
    print(f"\nTotal CVs válidos: {total_valid}/{total_valid + total_invalid}")
    return total_valid, total_invalid

def validate_wikipedia(validator: DataValidator, verbose: bool = False) -> Tuple[int, int]:
    """Valida documentos de Wikipedia (si existe el esquema)"""    
    # print("VALIDANDO WIKIPEDIA")
    
    total_valid = 0
    total_invalid = 0
    
    # Validar Wikipedia en español
    # print("[ES] Validando documentos de Wikipedia en español...")
    results_es = validator.validate_directory('data/wikipedia/es/json', 'wikipedia_schema', '*.json')
    
    if results_es:
        total_valid += sum(1 for is_valid, _ in results_es.values() if is_valid)
        total_invalid += sum(1 for is_valid, _ in results_es.values() if not is_valid)
    else:
        logger.warning("No se encontraron archivos para validar en data/wikipedia/es/json")
    
    # Validar Wikipedia en inglés
    # print("[EN] Validando documentos de Wikipedia en inglés...")
    results_en = validator.validate_directory('data/wikipedia/en/json', 'wikipedia_schema', '*.json')
    
    if results_en:
        total_valid += sum(1 for is_valid, _ in results_en.values() if is_valid)
        total_invalid += sum(1 for is_valid, _ in results_en.values() if not is_valid)
    else:
        logger.warning("No se encontraron archivos para validar en data/wikipedia/en/json")
    
    print(f"\nTotal documentos Wikipedia válidos: {total_valid}/{total_valid + total_invalid}")
    return total_valid, total_invalid


def main():
    """Función principal que ejecuta todas las validaciones"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Valida archivos JSON contra esquemas predefinidos')
    parser.add_argument('--cvs', action='store_true', help='Validar solo CVs')
    parser.add_argument('--wikipedia', action='store_true', help='Validar solo Wikipedia')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar detalles de errores')
    parser.add_argument('--file', type=str, help='Validar un archivo específico contra un esquema')
    parser.add_argument('--schema', type=str, help='Esquema a usar para validación de archivo específico')
    
    args = parser.parse_args()
    
    validator = DataValidator()
    
    # Si no hay esquemas cargados
    if not validator.schemas:
        logger.error("No se encontraron esquemas. Verifica la carpeta 'schemas/'")
        return
    
    # print(f"Esquemas disponibles: {', '.join(validator.schemas.keys())}\n")
    
    total_valid = 0
    total_invalid = 0
    
    # Validar archivo específico
    if args.file and args.schema:
        # print(f"\nValidando archivo específico: {args.file}")
        is_valid, errors = validator.validate_file(args.file, args.schema)
        
        # if is_valid:
        #     print("[OK] Archivo válido")
        if not is_valid:
            logger.error("[FAIL] Archivo inválido:")
            for error in errors:
                logger.error(f"   └─ {error}")
        return
    
    # Validar todo o según filtros
    validate_all = not (args.cvs or args.wikipedia)
    
    if args.cvs or validate_all:
        cvs_valid, cvs_invalid = validate_cvs(validator, args.verbose)
        total_valid += cvs_valid
        total_invalid += cvs_invalid
    
    if args.wikipedia or validate_all:
        wiki_valid, wiki_invalid = validate_wikipedia(validator, args.verbose)
        total_valid += wiki_valid
        total_invalid += wiki_invalid
    
    # Resumen final
    # print("RESUMEN FINAL")
    # print(f"Total válidos: {total_valid}")
    # print(f"Total inválidos: {total_invalid}")
    # print(f"Tasa de validación: {total_valid/(total_valid+total_invalid)*100:.1f}%" if (total_valid+total_invalid) > 0 else "Sin datos")


# if __name__ == "__main__":
#     main()