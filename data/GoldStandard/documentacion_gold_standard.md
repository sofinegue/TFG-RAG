# Documentación del Gold Standard — Caso de uso: CVs en Español

## 1. Introducción

El **gold standard** (o *ground truth*) es un conjunto de pares pregunta-respuesta cuya corrección ha sido verificada de forma determinista. Su propósito es servir como referencia objetiva para evaluar la calidad de las respuestas de un sistema RAG (*Retrieval-Augmented Generation*). Al comparar las respuestas del sistema con las del gold standard, se pueden calcular métricas de rendimiento como precisión, recall, F1-score y exactitud.

En esta sección se documenta el proceso de generación del gold standard para el **caso de uso de CVs en español**, que constituye el primero de los tres casos de uso evaluados en este trabajo.

---

## 2. Datos de partida

| Parámetro | Valor |
|---|---|
| Directorio de CVs | `data/cvs/es/` |
| Número total de CVs | 300 |
| Formato de los CVs | JSON |
| Idioma | Español |

### 2.1 Estructura de cada CV

Cada archivo JSON de CV contiene los siguientes campos:

```json
{
  "nombre_apellidos": "string",
  "puesto": "string",
  "experiencia": ["string", ...],
  "estudios": ["string", ...],
  "hard_skills": ["string", ...],
  "soft_skills": ["string", ...],
  "otros": ["string", ...]
}
```

- **nombre_apellidos**: Nombre completo del candidato.
- **puesto**: Cargo o rol profesional actual.
- **experiencia**: Lista de frases que describen la trayectoria profesional.
- **estudios**: Titulaciones académicas (grados, FP, másteres, doctorados).
- **hard_skills**: Habilidades técnicas (lenguajes, frameworks, herramientas).
- **soft_skills**: Competencias blandas o interpersonales.
- **otros**: Información adicional: idiomas, certificaciones, preferencias laborales, etc.

---

## 3. Metodología de generación

### 3.1 Enfoque: generación determinista basada en datos

Se optó por un enfoque **computacional y determinista** en lugar de utilizar un LLM para generar las respuestas. Las razones de esta decisión son:

1. **Corrección garantizada**: Las respuestas se computan directamente de los datos fuente mediante operaciones de filtrado, conteo y agregación. No existe posibilidad de alucinación ni de errores factuales.
2. **Reproducibilidad**: El script produce siempre el mismo resultado con los mismos datos de entrada (semilla aleatoria fija: `seed=42`).
3. **Trazabilidad**: Cada respuesta puede ser verificada de forma independiente consultando los archivos JSON originales.

### 3.2 Proceso paso a paso

El proceso de generación se implementó en un script Python (`scripts/generar_gold_standard_cvs_es.py`) que ejecuta las siguientes fases:

#### Fase 1: Carga de datos
Se cargan los 300 archivos JSON de CVs del directorio `data/cvs/es/`.

#### Fase 2: Construcción de índices invertidos
Se construyen estructuras de datos que permiten búsquedas eficientes:

- **`idx_hard_skill`**: Mapeo de cada hard skill → lista de personas que la poseen.
- **`idx_soft_skill`**: Mapeo de cada soft skill → lista de personas.
- **`idx_puesto`**: Mapeo de cada puesto → lista de personas.
- **`idx_estudio`**: Mapeo de cada titulación → lista de personas.
- **`idx_otro`**: Mapeo de cada entrada de "otros" → lista de personas.
- **`idx_nombre_cv`**: Mapeo de nombre completo → identificador de CV.

Adicionalmente se computan contadores de frecuencia para skills, puestos, estudios y estadísticas por persona (número de skills, estudios, experiencias, etc.).

#### Fase 3: Generación de preguntas con formulaciones únicas
Se definen **220 preguntas**, cada una con una formulación lingüísticamente distinta. Las preguntas se organizan en 12 categorías (ver sección 4). Para garantizar la unicidad: 

- Cada pregunta se escribe con una plantilla textual diferente (no se reutilizan patrones sintácticos).
- Los valores concretos (skills, puestos, nombres) se seleccionan aleatoriamente de los índices invertidos.
- Al final del proceso se verifica programáticamente que no existan preguntas duplicadas.

#### Fase 4: Cómputo de respuestas
Para cada pregunta, la respuesta se calcula directamente:

- **Preguntas de búsqueda**: Se consultan los índices invertidos para obtener la lista completa de personas que cumplen el criterio.
- **Preguntas de conteo**: Se aplica `len()` sobre los resultados filtrados.
- **Preguntas multi-criterio**: Se combinan múltiples filtros con operadores lógicos AND.
- **Preguntas de existencia**: Se verifica la condición y se devuelve un booleano junto con las personas encontradas.
- **Preguntas de agregación**: Se utilizan `Counter.most_common()`, `max()`, `mean()` y distribuciones.

#### Fase 5: Validación y exportación
Se verifican las siguientes condiciones antes de exportar:
- Todas las preguntas son textualmente únicas.
- Cada entrada tiene los campos obligatorios (`id`, `categoria`, `pregunta`, `respuesta`, `tipo_respuesta`).

El resultado se exporta como un archivo JSON en `data/GoldStandard/gold_standard_cvs_es.json`.

---

## 4. Categorías de preguntas

Se definieron **12 categorías** que cubren exhaustivamente los tipos de consulta que un usuario podría realizar sobre una base de datos de CVs:

| # | Categoría | N.º preguntas | Descripción |
|---|---|---|---|
| 1 | `busqueda_por_skill` | 25 | Buscar todas las personas que posean una hard skill concreta |
| 2 | `busqueda_por_puesto` | 20 | Buscar todas las personas con un puesto específico |
| 3 | `busqueda_por_formacion` | 20 | Buscar personas por titulación académica |
| 4 | `busqueda_por_idioma` | 15 | Buscar por idiomas, preferencias laborales u otros datos complementarios |
| 5 | `consulta_individual` | 25 | Consultar datos específicos de una persona concreta (puesto, skills, estudios, etc.) |
| 6 | `consulta_experiencia` | 15 | Consultar la experiencia laboral de una persona |
| 7 | `conteo` | 20 | Preguntas cuya respuesta es un número (cuántos candidatos cumplen X) |
| 8 | `multi_criterio` | 25 | Preguntas que combinan 2 o más criterios de filtrado simultáneamente |
| 9 | `existencia` | 15 | Preguntas de tipo sí/no con detalle de las personas encontradas |
| 10 | `agregacion` | 20 | Rankings, promedios, distribuciones y extremos estadísticos |
| 11 | `busqueda_por_soft_skill` | 10 | Buscar personas por competencia blanda |
| 12 | `busqueda_por_experiencia` | 10 | Buscar personas cuya experiencia contenga un keyword específico |
| | **Total** | **220** | |

### 4.1 Justificación del diseño de categorías

- **Cobertura de campos**: Cada campo del CV (puesto, hard_skills, soft_skills, estudios, experiencia, otros) tiene al menos una categoría dedicada.
- **Preguntas de conjuntos completos**: Las categorías 1-4 y 11-12 exigen que el sistema devuelva **todas** las personas que cumplen un criterio, evaluando así la exhaustividad del recall del sistema RAG.
- **Complejidad creciente**: Las categorías van de consultas simples (un criterio) a complejas (multi-criterio, agregaciones).
- **Variedad de tipo de respuesta**: Se incluyen listas de personas, valores únicos, números, booleanos, rankings y distribuciones.

---

## 5. Tipos de respuesta

| Tipo | N.º preguntas | Descripción |
|---|---|---|
| `lista_personas` | 124 | Lista de nombres completos que cumplen el criterio |
| `numero` | 23 | Respuesta numérica (conteo, media, total) |
| `lista_experiencia` | 15 | Lista de entradas de experiencia de un CV |
| `booleano_con_detalle` | 15 | Indica si existe alguien que cumpla el criterio, con lista de personas |
| `lista_skills` | 10 | Lista de skills de una persona |
| `ranking` | 10 | Lista ordenada de elementos con su frecuencia |
| `valor_unico` | 7 | Un solo valor (ej: el puesto de una persona) |
| `valor_con_detalle` | 6 | Un valor con información adicional (ej: persona + cantidad) |
| `lista_estudios` | 5 | Lista de titulaciones de una persona |
| `lista_otros` | 3 | Lista de información adicional de una persona |
| `lista_personas_con_conteo` | 1 | Lista de personas junto con el conteo total |
| `distribucion` | 1 | Distribución estadística (ej: personas por nº de skills) |

---

## 6. Formato del archivo de salida

El archivo generado `gold_standard_cvs_es.json` tiene la siguiente estructura:

```json
{
  "gold_standard": {
    "caso_uso": "cvs",
    "idioma": "es",
    "total_preguntas": 220,
    "total_cvs_analizados": 300,
    "fecha_generacion": "2026-04-17",
    "categorias": { ... },
    "descripcion": "...",
    "preguntas": [
      {
        "id": 1,
        "categoria": "busqueda_por_skill",
        "pregunta": "¿Qué personas dominan UML?",
        "tipo_respuesta": "lista_personas",
        "respuesta": ["Damián Ribas Márquez", ...],
        "num_resultados": 5
      },
      ...
    ]
  }
}
```

### 6.1 Campos de cada pregunta

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | int | Identificador secuencial único (1-220) |
| `categoria` | string | Categoría de la pregunta (ver sección 4) |
| `pregunta` | string | Texto completo de la pregunta en lenguaje natural |
| `tipo_respuesta` | string | Tipo de dato de la respuesta (ver sección 5) |
| `respuesta` | variable | La respuesta correcta (puede ser string, lista, número, objeto o booleano) |
| `num_resultados` | int | (Solo listas) Número de elementos en la respuesta |
| `cv_referencia` | string | (Solo consultas individuales) Identificador del CV consultado |

---

## 7. Ejemplos representativos

### 7.1 Búsqueda por skill (conjunto completo)

```json
{
  "id": 1,
  "categoria": "busqueda_por_skill",
  "pregunta": "¿Qué personas dominan UML?",
  "tipo_respuesta": "lista_personas",
  "respuesta": ["Damián Ribas Márquez", "Hugo Vilar Bayo", ...],
  "num_resultados": 5
}
```

### 7.2 Consulta individual

```json
{
  "id": 86,
  "categoria": "consulta_individual",
  "pregunta": "¿Cuál es el puesto de Valentina Rivas Arias?",
  "tipo_respuesta": "valor_unico",
  "respuesta": "Backend Developer",
  "cv_referencia": "cv_157"
}
```

### 7.3 Multi-criterio

```json
{
  "id": 131,
  "categoria": "multi_criterio",
  "pregunta": "¿Qué personas saben tanto AWS Lambda como Docker?",
  "tipo_respuesta": "lista_personas",
  "respuesta": ["Ana López García"],
  "num_resultados": 1
}
```

### 7.4 Agregación

```json
{
  "id": 181,
  "categoria": "agregacion",
  "pregunta": "¿Cuáles son las 5 hard skills más frecuentes entre todos los candidatos?",
  "tipo_respuesta": "ranking",
  "respuesta": [
    {"skill": "Python", "frecuencia": 42},
    {"skill": "Docker", "frecuencia": 38},
    ...
  ]
}
```

### 7.5 Existencia

```json
{
  "id": 163,
  "categoria": "existencia",
  "pregunta": "¿Hay alguien que hable tanto alemán como francés?",
  "tipo_respuesta": "booleano_con_detalle",
  "respuesta": {
    "existe": true,
    "personas": ["Laura Méndez Soto", "Pedro Ruíz Fernández"]
  }
}
```

---

## 8. Garantías de calidad

| Propiedad | Mecanismo de verificación |
|---|---|
| **Corrección de respuestas** | Cómputo directo sobre los datos fuente (sin intervención de LLM) |
| **Unicidad de preguntas** | Verificación programática: 220 preguntas únicas de 220 totales |
| **Reproducibilidad** | Semilla aleatoria fija (`random.seed(42)`) |
| **Cobertura de campos** | Los 7 campos del CV están representados en las categorías |
| **Diversidad lingüística** | 220 plantillas textuales distintas escritas manualmente |
| **Balance de dificultad** | Desde consultas de 1 criterio hasta filtros multi-criterio y agregaciones |

---

## 9. Estadísticas del gold standard generado

| Métrica | Valor |
|---|---|
| Total de preguntas | 220 |
| CVs analizados | 300 |
| Categorías de preguntas | 12 |
| Tipos de respuesta distintos | 12 |
| Preguntas únicas verificadas | 220/220 (100%) |
| Tamaño del archivo JSON | 114,5 KB |
| Fecha de generación | 17 de abril de 2026 |

---

## 10. Archivos generados

| Archivo | Ubicación | Descripción |
|---|---|---|
| Script de generación | `data/GoldStandard/scripts/generar_gold_standard_cvs_es.py` | Script Python que carga los CVs, construye índices y genera el gold standard |
| Gold standard | `data/GoldStandard/gold_standard_cvs_es.json` | Archivo JSON con las 220 preguntas y respuestas verificadas |
| Documentación | `data/GoldStandard/documentacion_gold_standard.md` | Este documento |

---

## 11. Uso previsto

El gold standard se utilizará en la fase de evaluación del sistema RAG de la siguiente manera:

1. Se envía cada pregunta del gold standard al sistema RAG.
2. Se recoge la respuesta generada por el sistema.
3. Se compara la respuesta del sistema con la respuesta de referencia del gold standard.
4. Se calculan métricas de evaluación:
   - **Precisión**: Proporción de elementos en la respuesta del sistema que son correctos.
   - **Recall**: Proporción de elementos de la respuesta correcta que el sistema logró recuperar.
   - **F1-Score**: Media armónica de precisión y recall.
   - **Exactitud (Exact Match)**: Proporción de preguntas donde la respuesta del sistema coincide exactamente con el gold standard.
   - Métricas específicas por categoría y tipo de respuesta.
