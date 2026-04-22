# Documentación del Gold Standard — Evaluación del Sistema RAG

## 1. Introducción

El **gold standard** (o *ground truth*) es un conjunto de pares pregunta-respuesta cuya corrección ha sido verificada de forma determinista. Su propósito es servir como referencia objetiva para evaluar la calidad de las respuestas de un sistema RAG (*Retrieval-Augmented Generation*). Al comparar las respuestas del sistema con las del gold standard, se pueden calcular métricas de rendimiento como precisión, recall, F1-score y exactitud.

En este proyecto se han generado **seis gold standards** que cubren tres casos de uso en dos idiomas cada uno:

| # | Caso de uso | Idioma | Preguntas | Documentos analizados |
|---|---|---|---|---|
| 1 | CVs | Español | 220 | 300 CVs |
| 2 | CVs | Inglés | 220 | 300 CVs |
| 3 | Wikipedia | Español | 200 | 182 artículos |
| 4 | Wikipedia | Inglés | 200 | 133 artículos |
| 5 | Documentos UE | Español | 206 | 19 documentos del DOUE |
| 6 | Documentos UE | Inglés | *(pendiente de disponer de los PDFs en inglés)* | — |
| | **Total** | | **1046** | |

Cada gold standard ha sido generado mediante un enfoque **computacional y determinista**, sin intervención de modelos de lenguaje en la producción de respuestas, lo que garantiza una corrección del 100 % frente a los datos fuente.

---

## 2. Datos de partida

### 2.1 Caso de uso 1: CVs (Español e Inglés)

| Parámetro | Español | Inglés |
|---|---|---|
| Directorio | `data/cvs/es/` | `data/cvs/en/` |
| Número total de CVs | 300 | 300 |
| Formato | JSON | JSON |

#### Estructura de cada CV

Cada archivo JSON de CV contiene los siguientes campos (idénticos en ambos idiomas):

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

### 2.2 Caso de uso 2: Wikipedia (Español e Inglés)

| Parámetro | Español | Inglés |
|---|---|---|
| Directorio | `data/wikipedia/es/json/` | `data/wikipedia/en/json/` |
| Número de artículos | 182 | 133 |
| Temática | Literatura y movimientos literarios | Literatura y movimientos literarios |
| Formato | JSON | JSON |

#### Estructura de cada artículo

```json
{
  "titulo": "string",
  "idioma": "es | en",
  "pageid": "int",
  "categorias": ["string", ...],
  "url": "string",
  "contenido": "string (texto completo con markdown)",
  "fecha_descarga": "string (ISO timestamp)"
}
```

- **titulo**: Título del artículo de Wikipedia.
- **idioma**: Código de idioma (`es` o `en`).
- **pageid**: Identificador numérico de la página en Wikipedia.
- **categorias**: Lista de categorías de Wikipedia a las que pertenece el artículo.
- **url**: Enlace al artículo original en Wikipedia.
- **contenido**: Texto completo del artículo, incluyendo marcado de secciones (`== Sección ==`).
- **fecha_descarga**: Fecha y hora en que se descargó el artículo.

### 2.3 Caso de uso 3: Documentos de la Unión Europea (Español)

| Parámetro | Valor |
|---|---|
| Directorio de PDFs | `data/eu/es/` |
| Directorio de JSONs extraídos | `data/eu/es/json/` |
| Número de documentos | 19 |
| Fuente | Diario Oficial de la Unión Europea (Serie L) |
| Formato original | PDF |
| Formato procesado | JSON (tras extracción con `pdfplumber`) |

#### Proceso de extracción de PDFs

Los documentos de la UE se distribuyen en formato PDF. Para poder procesarlos computacionalmente, se implementó un script de extracción (`scripts/extraer_pdfs_eu.py`) que:

1. Abre cada PDF con la librería `pdfplumber`.
2. Extrae el texto de cada página individualmente, con manejo robusto de errores por página.
3. Silencia el logging verbose de `pdfminer` para evitar interrupciones en documentos complejos.
4. Omite archivos ya extraídos (ejecución incremental) para gestionar documentos de gran tamaño (el mayor tiene 2.400 páginas).
5. Genera un archivo JSON por cada PDF con la siguiente estructura:

```json
{
  "archivo": "OJ_L_202600193_ES.pdf",
  "idioma": "es",
  "num_paginas": 4,
  "contenido": "texto completo concatenado de todas las páginas",
  "paginas": ["texto página 1", "texto página 2", ...]
}
```

#### Tipología de documentos de la UE

Los 19 documentos se distribuyen en los siguientes tipos:

| Tipo de documento | Cantidad |
|---|---|
| Reglamentos (de ejecución, delegados, ordinarios) | 10 |
| Decisiones (de ejecución, PESC, ordinarias) | 8 |
| Corrección de errores | 1 |

Los documentos cubren temáticas diversas: pesca y cuotas pesqueras, productos sanitarios, medidas restrictivas (sanciones), acuerdos internacionales (Marruecos, Túnez), plaguicidas, indicaciones geográficas, normas armonizadas, y política exterior y de seguridad común.

---

## 3. Metodología de generación

### 3.1 Enfoque: generación determinista basada en datos

Se optó por un enfoque **computacional y determinista** en lugar de utilizar un LLM para generar las respuestas. Las razones de esta decisión son:

1. **Corrección garantizada**: Las respuestas se computan directamente de los datos fuente mediante operaciones de filtrado, conteo y agregación. No existe posibilidad de alucinación ni de errores factuales.
2. **Reproducibilidad**: Todos los scripts producen siempre el mismo resultado con los mismos datos de entrada (semilla aleatoria fija: `seed=42`).
3. **Trazabilidad**: Cada respuesta puede ser verificada de forma independiente consultando los archivos fuente originales.
4. **Escalabilidad**: La misma metodología se aplica a los tres casos de uso, adaptando las categorías de preguntas y los índices invertidos al tipo de dato.

### 3.2 Proceso general (común a todos los casos de uso)

Cada script de generación implementa las siguientes fases:

#### Fase 1: Carga de datos
Se cargan todos los archivos JSON del directorio correspondiente al caso de uso e idioma.

#### Fase 2: Construcción de índices
Se construyen estructuras de datos (diccionarios invertidos, contadores, estadísticas) que permiten responder eficientemente a cada tipo de pregunta. La naturaleza de los índices varía según el caso de uso:

| Caso de uso | Índices principales |
|---|---|
| CVs | Skill → personas, puesto → personas, estudio → personas, nombre → CV |
| Wikipedia | Categoría → artículos, secciones por artículo, palabras por artículo, búsqueda textual |
| Documentos UE | Tipo de documento → docs, órgano emisor → docs, referencias cruzadas, metadatos regulatorios |

#### Fase 3: Generación de preguntas con formulaciones únicas
Se definen entre 200 y 220 preguntas por gold standard, cada una con una **formulación lingüísticamente distinta**. Esto es un requisito clave: no se reutilizan patrones sintácticos idénticos ni siquiera dentro de la misma categoría. Se garantiza la unicidad verificando programáticamente que no existan preguntas duplicadas al final de la generación.

#### Fase 4: Cómputo de respuestas
Para cada pregunta, la respuesta se calcula directamente desde los datos:

- **Preguntas de búsqueda**: Se consultan los índices invertidos.
- **Preguntas de conteo**: Se aplica `len()` sobre los resultados filtrados.
- **Preguntas multi-criterio**: Se combinan múltiples filtros con operadores lógicos.
- **Preguntas de existencia**: Se verifica la condición y se devuelve un booleano con detalle.
- **Preguntas de agregación**: Se utilizan `Counter.most_common()`, `max()`, `mean()` y distribuciones.

#### Fase 5: Validación y exportación
Se verifican que todas las preguntas sean textualmente únicas y que cada entrada contenga los campos obligatorios. El resultado se exporta como JSON.

### 3.3 Adaptaciones específicas por caso de uso

#### CVs (ES / EN)
- **Índices invertidos** por cada campo del CV: hard_skills, soft_skills, puesto, estudios, experiencia, otros.
- Las preguntas en inglés utilizan palabras clave adaptadas al idioma (p. ej., *"remote"* en lugar de *"remoto"*, *"self-taught"* en lugar de *"Autodidacta"*).
- Se incluyen preguntas multi-criterio que combinan 2-3 campos simultáneamente.

#### Wikipedia (ES / EN)
- Se extraen las **secciones** de cada artículo mediante expresiones regulares sobre las marcas `== Sección ==`.
- Se calcula la **primera frase** de cada artículo como definición/resumen.
- Se construye un índice de **categorías** limpio, excluyendo categorías internas de Wikipedia (p. ej., *"Articles with short description"*, *"Wikipedia:*").
- La búsqueda por contenido se realiza mediante coincidencia textual (*case-insensitive*) en el cuerpo del artículo.

#### Documentos UE (ES)
- Se ejecuta una **fase previa de extracción de PDFs** a JSON mediante `pdfplumber`.
- Se analizan los metadatos regulatorios de cada documento: tipo (Reglamento/Decisión/Corrección), código numérico, órgano emisor, fecha de adopción, número de artículos, número de considerandos.
- Se construye un índice de **referencias cruzadas**: cada documento cita otros reglamentos/decisiones de la UE, lo que permite preguntas sobre relaciones entre documentos.
- Se incluyen preguntas sobre el contenido jurídico específico: ámbito de aplicación, entrada en vigor, derogaciones, disposiciones transitorias, destinatarios.

---

## 4. Categorías de preguntas por caso de uso

### 4.1 CVs (Español e Inglés) — 220 preguntas cada uno

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

**Justificación del diseño:**
- Cada campo del CV (puesto, hard_skills, soft_skills, estudios, experiencia, otros) tiene al menos una categoría dedicada.
- Las categorías de búsqueda exigen que el sistema devuelva **todas** las personas que cumplen un criterio, evaluando la exhaustividad del recall.
- La complejidad crece progresivamente: consultas simples → multi-criterio → agregaciones.
- Se incluyen listas de personas, valores únicos, números, booleanos, rankings y distribuciones.

### 4.2 Wikipedia (Español e Inglés) — 200 preguntas cada uno

Se definieron **10 categorías** adaptadas a la naturaleza de artículos enciclopédicos de texto libre:

| # | Categoría (ES / EN) | N.º preguntas | Descripción |
|---|---|---|---|
| 1 | `definicion` / `definition` | 30 | ¿Qué es X? — Primera frase del artículo como respuesta |
| 2 | `secciones` / `sections` | 20 | Estructura interna del artículo (encabezados `== ==`) |
| 3 | `categorias_articulo` / `article_categories` | 15 | Categorías de Wikipedia asignadas al artículo |
| 4 | `busqueda_por_categoria` / `search_by_category` | 20 | Artículos que pertenecen a una categoría concreta |
| 5 | `busqueda_por_contenido` / `search_by_content` | 25 | Artículos que mencionan una palabra clave en su texto |
| 6 | `metadatos` / `metadata` | 15 | URL, page ID, idioma, fecha de descarga, estadísticas |
| 7 | `conteo` / `counting` | 20 | Estadísticas numéricas: totales, medias, extremos |
| 8 | `existencia` / `existence` | 15 | ¿Existe un artículo sobre X? ¿Se menciona Y en algún artículo? |
| 9 | `listado` / `listing` | 10 | Catálogo completo o filtrado de artículos |
| 10 | `relaciones` / `relationships` | 30 | Comparaciones, rankings, artículos por país, inter-referencias |
| | **Total** | **200** | |

**Diferencias clave respecto al caso de CVs:**
- Los datos son **texto libre** (no estructurado), por lo que las búsquedas se realizan por coincidencia textual en el contenido.
- Se aprovechan las **categorías de Wikipedia** como dato estructurado para preguntas de clasificación.
- Se extraen las **secciones** de los artículos mediante expresiones regulares.
- Las preguntas de definición utilizan la primera frase del artículo como respuesta de referencia.

### 4.3 Documentos de la UE (Español) — 206 preguntas

Se definieron **10 categorías** diseñadas para documentos legislativos y regulatorios:

| # | Categoría | N.º preguntas | Descripción |
|---|---|---|---|
| 1 | `identificacion` | 25 | Tipo, título, fecha, órgano emisor y metadatos de un documento concreto |
| 2 | `busqueda_por_tipo` | 15 | Filtrar documentos por tipo (reglamento, decisión, etc.) u órgano emisor |
| 3 | `busqueda_por_contenido` | 30 | Buscar documentos que traten sobre un tema concreto (pesca, sanciones, etc.) |
| 4 | `conteo` | 24 | Estadísticas: totales, medias, rankings, distribuciones por tipo |
| 5 | `referencias_cruzadas` | 18 | Reglamentos/decisiones citados dentro de cada documento y relaciones inter-documentales |
| 6 | `estructura` | 16 | Número de artículos, considerandos, anexos, disposiciones especiales |
| 7 | `existencia` | 20 | ¿Hay documentos sobre X? ¿Se menciona Y? (con detalle de documentos) |
| 8 | `listado` | 13 | Catálogo completo, por órgano, por tipo, por año |
| 9 | `relaciones` | 24 | Comparaciones, agrupaciones temáticas, distribución temporal, países mencionados |
| 10 | `contenido_especifico` | 21 | Artículos concretos, ámbito de aplicación, derogaciones, bases jurídicas, plazos |
| | **Total** | **206** | |

**Particularidades del caso UE:**
- Incluye una **fase previa de extracción de PDFs** a JSON, necesaria porque los documentos originales están en formato PDF.
- Se extraen metadatos regulatorios de forma automatizada: tipo de acto jurídico, código numérico, órgano emisor, fecha de adopción, número de artículos y considerandos.
- Se analizan las **referencias cruzadas** entre documentos (citas a otros reglamentos y decisiones de la UE).
- Las preguntas cubren aspectos específicos del derecho de la UE: entrada en vigor, disposiciones transitorias, derogaciones, destinatarios, bases jurídicas.

---

## 5. Formato de los archivos de salida

### 5.1 Estructura general

Todos los gold standards comparten una estructura JSON uniforme:

```json
{
  "gold_standard": {
    "caso_uso": "cvs | wikipedia | documentos_ue",
    "idioma": "es | en",
    "total_preguntas": N,
    "total_cvs_analizados | total_articulos_analizados | total_documentos_analizados": M,
    "fecha_generacion": "2026-04-17",
    "categorias": { "nombre_categoria": cantidad, ... },
    "descripcion": "...",
    "preguntas": [ ... ]
  }
}
```

### 5.2 Campos de cada pregunta

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | int | Identificador secuencial único |
| `categoria` / `category` | string | Categoría de la pregunta |
| `pregunta` / `question` | string | Texto completo de la pregunta en lenguaje natural |
| `tipo_respuesta` / `answer_type` | string | Tipo de dato de la respuesta |
| `respuesta` / `answer` | variable | La respuesta correcta (string, lista, número, objeto o booleano) |
| `num_resultados` / `num_results` | int | (Solo listas) Número de elementos en la respuesta |

> **Nota sobre la nomenclatura**: Los gold standards en español usan campos en español (`pregunta`, `respuesta`, `tipo_respuesta`), mientras que los de inglés usan campos en inglés (`question`, `answer`, `answer_type`). Esto facilita el procesamiento coherente con el idioma del gold standard.

---

## 6. Ejemplos representativos

### 6.1 CVs — Búsqueda por skill

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

### 6.2 CVs — Multi-criterio

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

### 6.3 Wikipedia — Definición

```json
{
  "id": 1,
  "categoria": "definicion",
  "pregunta": "¿Qué es Realismo mágico?",
  "tipo_respuesta": "texto",
  "respuesta": "El realismo mágico es un movimiento literario que..."
}
```

### 6.4 Wikipedia — Búsqueda por contenido

```json
{
  "id": 75,
  "categoria": "busqueda_por_contenido",
  "pregunta": "¿Qué artículos mencionan a García Márquez?",
  "tipo_respuesta": "lista_articulos",
  "respuesta": ["Boom latinoamericano", "Realismo mágico", ...],
  "num_resultados": 8
}
```

### 6.5 Documentos UE — Identificación

```json
{
  "id": 3,
  "categoria": "identificacion",
  "pregunta": "¿Quién emitió el documento 2025/2649?",
  "tipo_respuesta": "lista",
  "respuesta": ["Consejo", "Parlamento Europeo"]
}
```

### 6.6 Documentos UE — Existencia

```json
{
  "id": 120,
  "categoria": "existencia",
  "pregunta": "¿Hay documentos que traten sobre Ucrania?",
  "tipo_respuesta": "booleano",
  "respuesta": {
    "existe": true,
    "documentos": ["OJ_L_202600271_ES"]
  }
}
```

### 6.7 Documentos UE — Referencias cruzadas

```json
{
  "id": 88,
  "categoria": "referencias_cruzadas",
  "pregunta": "¿A qué otros reglamentos hace referencia el documento 2026/215?",
  "tipo_respuesta": "lista_referencias",
  "respuesta": ["2005/396", "2017/625", ...],
  "num_resultados": 4
}
```

---

## 7. Garantías de calidad

| Propiedad | Mecanismo de verificación | Aplica a |
|---|---|---|
| **Corrección de respuestas** | Cómputo directo sobre los datos fuente (sin intervención de LLM) | Todos |
| **Unicidad de preguntas** | Verificación programática al final de cada script | Todos |
| **Reproducibilidad** | Semilla aleatoria fija (`random.seed(42)`) | Todos |
| **Cobertura de campos** | Los campos relevantes de cada fuente están representados | Todos |
| **Diversidad lingüística** | Plantillas textuales distintas, escritas manualmente, sin reutilización de patrones | Todos |
| **Balance de dificultad** | Desde consultas simples hasta multi-criterio, agregaciones y relaciones | Todos |
| **Integridad de datos** | Extracción de PDFs con manejo robusto de errores por página | Documentos UE |

---

## 8. Estadísticas de los gold standards generados

| Gold Standard | Preguntas | Fuentes | Categorías | Preguntas únicas | Fecha |
|---|---|---|---|---|---|
| CVs ES | 220 | 300 CVs | 12 | 220/220 (100 %) | 17/04/2026 |
| CVs EN | 220 | 300 CVs | 12 | 220/220 (100 %) | 17/04/2026 |
| Wikipedia ES | 200 | 182 artículos | 10 | 200/200 (100 %) | 17/04/2026 |
| Wikipedia EN | 200 | 133 artículos | 10 | 200/200 (100 %) | 17/04/2026 |
| Documentos UE ES | 206 | 19 documentos DOUE | 10 | 206/206 (100 %) | 17/04/2026 |
| **Total** | **1.046** | | | **1.046/1.046** | |

---

## 9. Archivos generados

### 9.1 Gold standards (archivos JSON)

| Archivo | Ubicación | Descripción |
|---|---|---|
| Gold standard CVs ES | `data/GoldStandard/gold_standard_cvs_es.json` | 220 preguntas sobre CVs en español |
| Gold standard CVs EN | `data/GoldStandard/gold_standard_cvs_en.json` | 220 preguntas sobre CVs en inglés |
| Gold standard Wikipedia ES | `data/GoldStandard/gold_standard_wikipedia_es.json` | 200 preguntas sobre artículos de Wikipedia en español |
| Gold standard Wikipedia EN | `data/GoldStandard/gold_standard_wikipedia_en.json` | 200 preguntas sobre artículos de Wikipedia en inglés |
| Gold standard UE ES | `data/GoldStandard/gold_standard_eu_es.json` | 206 preguntas sobre documentos de la UE en español |

### 9.2 Scripts de generación

| Script | Ubicación | Descripción |
|---|---|---|
| Generador CVs ES | `data/GoldStandard/scripts/generar_gold_standard_cvs_es.py` | Carga CVs en español, construye índices y genera 220 preguntas |
| Generador CVs EN | `data/GoldStandard/scripts/generar_gold_standard_cvs_en.py` | Carga CVs en inglés, construye índices y genera 220 preguntas |
| Generador Wikipedia ES | `data/GoldStandard/scripts/generar_gold_standard_wikipedia_es.py` | Carga artículos de Wikipedia en español y genera 200 preguntas |
| Generador Wikipedia EN | `data/GoldStandard/scripts/generar_gold_standard_wikipedia_en.py` | Carga artículos de Wikipedia en inglés y genera 200 preguntas |
| Generador UE ES | `data/GoldStandard/scripts/generar_gold_standard_eu_es.py` | Carga documentos de la UE y genera 206 preguntas |
| Extractor de PDFs | `data/GoldStandard/scripts/extraer_pdfs_eu.py` | Convierte los PDFs de la UE a archivos JSON con `pdfplumber` |

### 9.3 Documentación

| Archivo | Ubicación | Descripción |
|---|---|---|
| Documentación técnica | `data/GoldStandard/documentacion_gold_standard.md` | Este documento |

---

## 10. Dependencias técnicas

| Librería | Versión utilizada | Propósito |
|---|---|---|
| Python | 3.11 | Lenguaje de ejecución |
| `pdfplumber` | 0.11.9 | Extracción de texto de PDFs de la UE |
| `pdfminer.six` | 20251230 | Motor de parsing de PDFs (dependencia de pdfplumber) |
| `Pillow` | 12.2.0 | Procesamiento de imágenes en PDFs (dependencia de pdfplumber) |

> Estas dependencias deben incluirse en el archivo `requirements.txt` del proyecto.

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

La evaluación se realizará de forma independiente para cada gold standard, permitiendo analizar el rendimiento del sistema RAG en función del caso de uso, del idioma y de la complejidad de las preguntas.

---

## 12. Consideraciones para la memoria del TFG

### 12.1 Contribución del gold standard

La generación de estos gold standards constituye una contribución metodológica del TFG por varias razones:

1. **Enfoque determinista**: A diferencia de trabajos que generan gold standards con LLMs (con riesgo de alucinación), aquí se garantiza la corrección de las respuestas al computarlas directamente desde los datos fuente.
2. **Diversidad lingüística**: Cada pregunta tiene una formulación única, lo que permite evaluar la capacidad del sistema RAG para comprender variaciones de lenguaje natural.
3. **Cobertura multi-dominio**: Se evalúa el mismo sistema RAG sobre tres dominios muy diferentes (recursos humanos, enciclopedia, legislación), lo que permite analizar su robustez.
4. **Bilingüismo**: La evaluación en español e inglés permite medir el impacto del idioma en la calidad de las respuestas.
5. **Escalabilidad de la metodología**: Los scripts son reutilizables y extensibles a nuevos dominios o idiomas.

### 12.2 Limitaciones conocidas

- **Dependencia de la calidad de los datos fuente**: Si los datos de partida contienen errores (p. ej., CVs con datos inconsistentes o PDFs mal formateados), las respuestas del gold standard heredarán esos errores.
- **Extracción de PDFs**: La conversión de PDF a texto puede perder formato (tablas, columnas, notas al pie), lo que puede afectar a la precisión de las respuestas basadas en contenido textual.
- **Cobertura temática**: Las preguntas cubren una selección amplia pero no exhaustiva de todas las posibles consultas. Un sistema RAG podría recibir preguntas no previstas en el gold standard.
- **Gold standard UE en inglés**: Pendiente de disponer de los documentos PDF en inglés para completar el conjunto.
