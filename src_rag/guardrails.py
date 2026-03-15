"""
GuardRails con LOGGING DETALLADO EN TERMINAL
Añadir al inicio de guardrails.py
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
from openai import AzureOpenAI
from config import config

# ✅ CONFIGURAR LOGGER PARA GUARDRAILS
logger = logging.getLogger("guardrails")
logger.setLevel(logging.INFO)

# Handler para consola con formato colorido
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formato detallado
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class GuardRailsViolation(Exception):
    """Excepción cuando se viola una regla de GuardRails"""
    pass


class InputGuardRails:
    """
    Validación de inputs del usuario CON LOGGING
    """
    
    def __init__(self):
        self.config = config
        
        chat_config = config.get_chat_model_config()
        self.openai_client = AzureOpenAI(
            api_key=chat_config.api_key,
            api_version=chat_config.api_version,
            azure_endpoint=chat_config.api_base
        )
        
        self.injection_patterns = [
            r"ignore\s+(previous|above|all)\s+instructions",
            r"disregard\s+.*\s+instructions",
            r"you\s+are\s+now\s+a\s+different",
            r"pretend\s+to\s+be",
            r"act\s+as\s+if\s+you\s+are",
            r"from\s+now\s+on",
            r"<script[^>]*>.*?</script>",
            r"eval\s*\(",
            r"exec\s*\(",
        ]
        
        self.suspicious_keywords = [
            "jailbreak", "bypass", "override", "sudo", "admin",
            "password", "token", "secret", "credential"
        ]
    
    def validate(self, query: str, user_id: str = "anonymous") -> Dict[str, any]:
        """Valida el input del usuario CON LOGGING DETALLADO"""
        
        logger.info("="*60)
        logger.info("🛡️  INPUT GUARDRAILS - VALIDACIÓN INICIADA")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Query: {query[:100]}{'...' if len(query) > 100 else ''}")
        logger.info("="*60)
        
        result = {
            "is_safe": True,
            "violations": [],
            "sanitized_query": query,
            "risk_level": "low",
            "timestamp": datetime.now().isoformat()
        }
        
        # 1. Validaciones básicas
        if not query or not query.strip():
            result["is_safe"] = False
            result["violations"].append("empty_query")
            result["risk_level"] = "low"
            logger.warning("❌ VIOLACIÓN: Query vacía")
            return result
        
        if len(query) > 5000:
            result["is_safe"] = False
            result["violations"].append("excessive_length")
            result["risk_level"] = "medium"
            logger.error(f"❌ VIOLACIÓN: Longitud excesiva ({len(query)} chars > 5000)")
            raise GuardRailsViolation("Query excede longitud máxima (5000 chars)")
        
        logger.info(f"✅ Longitud válida: {len(query)} chars")
        
        # 2. Detección de prompt injection
        injection_detected = self._detect_injection(query)
        if injection_detected:
            result["is_safe"] = False
            result["violations"].append("prompt_injection")
            result["risk_level"] = "high"
            logger.error(f"❌ VIOLACIÓN CRÍTICA: Prompt Injection detectado")
            logger.error(f"   Patrón encontrado: '{injection_detected}'")
            logger.error(f"   User: {user_id}")
            logger.error(f"   Query completa: {query}")
            raise GuardRailsViolation(f"Intento de inyección detectado: {injection_detected}")
        
        logger.info("✅ Sin prompt injection")
        
        # 3. Detección de palabras sospechosas
        suspicious = self._check_suspicious_keywords(query)
        if suspicious:
            result["violations"].append("suspicious_keywords")
            result["risk_level"] = "medium"
            result["suspicious_words"] = suspicious
            logger.warning(f"⚠️  SOSPECHA: Palabras clave detectadas: {suspicious}")
            logger.warning(f"   User: {user_id}")
        else:
            logger.info("✅ Sin palabras sospechosas")
        
        # 4. Moderación con OpenAI (opcional)
        if config.enable_content_moderation:
            logger.info("🔍 Ejecutando moderación de contenido...")
            moderation_result = self._moderate_content(query)
            if moderation_result["flagged"]:
                result["is_safe"] = False
                result["violations"].append("content_moderation")
                result["moderation_categories"] = moderation_result["categories"]
                result["risk_level"] = "high"
                logger.error(f"❌ VIOLACIÓN: Contenido inapropiado")
                logger.error(f"   Categorías: {moderation_result['categories']}")
                logger.error(f"   User: {user_id}")
                raise GuardRailsViolation(f"Contenido inapropiado: {moderation_result['categories']}")
            logger.info("✅ Moderación pasada")
        
        # 5. Sanitización
        result["sanitized_query"] = self._sanitize_query(query)
        if result["sanitized_query"] != query:
            logger.info(f"🧹 Query sanitizada (eliminados {len(query) - len(result['sanitized_query'])} chars)")
        
        logger.info("="*60)
        logger.info(f"✅ INPUT APROBADO - Risk Level: {result['risk_level']}")
        if result["violations"]:
            logger.info(f"   Violations (no críticas): {result['violations']}")
        logger.info("="*60)
        
        return result
    
    def _detect_injection(self, query: str) -> Optional[str]:
        """Detecta intentos de prompt injection"""
        query_lower = query.lower()
        
        for pattern in self.injection_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _check_suspicious_keywords(self, query: str) -> List[str]:
        """Verifica palabras clave sospechosas"""
        query_lower = query.lower()
        found = []
        
        for keyword in self.suspicious_keywords:
            if keyword in query_lower:
                found.append(keyword)
        
        return found
    
    def _moderate_content(self, query: str) -> Dict:
        """Usa OpenAI Moderation API"""
        try:
            response = self.openai_client.moderations.create(input=query)
            result = response.results[0]
            
            return {
                "flagged": result.flagged,
                "categories": [cat for cat, flagged in result.categories.model_dump().items() if flagged]
            }
        except Exception as e:
            logger.error(f"⚠️  Error en moderación: {e}")
            return {"flagged": False, "categories": []}
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitiza la query eliminando caracteres peligrosos"""
        sanitized = re.sub(r'<[^>]+>', '', query)
        sanitized = re.sub(r'[\x00-\x1F\x7F]', '', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized


class OutputGuardRails:
    """
    Validación de respuestas generadas CON LOGGING
    """
    
    def __init__(self):
        self.config = config
        
        chat_config = config.get_chat_model_config()
        self.openai_client = AzureOpenAI(
            api_key=chat_config.api_key,
            api_version=chat_config.api_version,
            azure_endpoint=chat_config.api_base
        )
        
        self.forbidden_patterns = [
            r"I cannot|I can't|I'm unable to",
            r"As an AI",
            r"I don't have access to",
        ]
        
        self.requires_disclaimer = [
            "médico", "salud", "diagnóstico", "tratamiento",
            "legal", "abogado", "ley", "contrato",
            "financiero", "inversión", "impuestos"
        ]
    
    def validate(
        self, 
        answer: str, 
        query: str, 
        chunks_used: List[Dict],
        metadata: Dict
    ) -> Dict[str, any]:
        """Valida la respuesta generada CON LOGGING DETALLADO"""
        
        logger.info("="*60)
        logger.info("🛡️  OUTPUT GUARDRAILS - VALIDACIÓN INICIADA")
        logger.info(f"Answer length: {len(answer)} chars")
        logger.info(f"Chunks used: {len(chunks_used)}")
        logger.info("="*60)
        
        result = {
            "is_compliant": True,
            "issues": [],
            "enhanced_answer": answer,
            "risk_level": "low",
            "timestamp": datetime.now().isoformat()
        }
        
        # 1. Validación de longitud
        if len(answer) < 10:
            result["is_compliant"] = False
            result["issues"].append("too_short")
            result["risk_level"] = "high"
            result["enhanced_answer"] = "Lo siento, no pude generar una respuesta adecuada."
            logger.error("❌ ISSUE CRÍTICO: Respuesta demasiado corta")
            return result
        
        logger.info(f"✅ Longitud válida: {len(answer)} chars")
        
        # 2. Verificar patrones prohibidos
        forbidden = self._check_forbidden_patterns(answer)
        if forbidden:
            result["issues"].append("forbidden_pattern")
            result["risk_level"] = "medium"
            result["forbidden_matches"] = forbidden
            logger.warning(f"⚠️  ISSUE: Patrones prohibidos encontrados: {forbidden}")
        else:
            logger.info("✅ Sin patrones prohibidos")
        
        # 3. Verificar si necesita disclaimer
        needs_disclaimer = self._check_disclaimer_needed(answer)
        if needs_disclaimer:
            result["issues"].append("missing_disclaimer")
            result["enhanced_answer"] = self._add_disclaimer(answer, needs_disclaimer)
            logger.info(f"📝 DISCLAIMER añadido para categorías: {needs_disclaimer}")
        else:
            logger.info("✅ No requiere disclaimer")
        
        # 4. Validar coherencia con chunks (detección de alucinaciones)
        if chunks_used and config.enable_hallucination_check:
            logger.info("🔍 Verificando posibles alucinaciones...")
            hallucination_score = self._detect_hallucination(answer, chunks_used)
            result["hallucination_score"] = hallucination_score
            
            if hallucination_score > 0.7:
                result["issues"].append("possible_hallucination")
                result["risk_level"] = "high"
                logger.error(f"❌ ISSUE CRÍTICO: Posible alucinación detectada (score: {hallucination_score:.2f})")
            else:
                logger.info(f"✅ Coherencia verificada (score: {hallucination_score:.2f})")
        
        # 5. Verificar límite de caracteres
        if len(answer) > config.max_answer_chars * 1.2:
            result["issues"].append("excessive_length")
            result["enhanced_answer"] = answer[:config.max_answer_chars] + "..."
            logger.warning(f"⚠️  ISSUE: Respuesta truncada ({len(answer)} > {config.max_answer_chars})")
        
        # 6. Validar formato HTML
        if not self._validate_html(answer):
            result["issues"].append("invalid_html")
            result["enhanced_answer"] = self._sanitize_html(answer)
            logger.warning("⚠️  ISSUE: HTML malformado - sanitizado")
        else:
            logger.info("✅ HTML válido")
        
        logger.info("="*60)
        if result["issues"]:
            logger.warning(f"⚠️  OUTPUT CON AJUSTES - Issues: {result['issues']}")
            logger.warning(f"   Risk Level: {result['risk_level']}")
        else:
            logger.info("✅ OUTPUT APROBADO SIN ISSUES")
        logger.info("="*60)
        
        return result
    
    def _check_forbidden_patterns(self, answer: str) -> List[str]:
        """Detecta patrones prohibidos"""
        found = []
        for pattern in self.forbidden_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                found.append(pattern)
        return found
    
    def _check_disclaimer_needed(self, answer: str) -> List[str]:
        """Verifica si necesita disclaimer legal/médico"""
        answer_lower = answer.lower()
        found = []
        
        for keyword in self.requires_disclaimer:
            if keyword in answer_lower:
                found.append(keyword)
        
        return found
    
    def _add_disclaimer(self, answer: str, categories: List[str]) -> str:
        """Añade disclaimer apropiado"""
        disclaimers = {
            "médico": "\n\n⚠️ **Aviso**: Esta información es solo orientativa. Consulta con un profesional de la salud.",
            "legal": "\n\n⚠️ **Aviso**: Esta información es general. Para asesoría legal específica, consulta con un abogado.",
            "financiero": "\n\n⚠️ **Aviso**: Esta información no constituye asesoría financiera. Consulta con un asesor profesional."
        }
        
        category = categories[0] if categories else None
        
        for key, disclaimer in disclaimers.items():
            if category and key in category:
                return answer + disclaimer
        
        return answer
    
    def _detect_hallucination(self, answer: str, chunks: List[Dict]) -> float:
        """
        Detecta posibles alucinaciones comparando con chunks
        VERSIÓN MEJORADA con análisis más preciso
        
        Returns:
            Score 0-1 (1 = alta probabilidad de alucinación)
        """
        try:
            # Extraer contexto de los chunks
            context = "\n\n".join([
                f"[Fuente {i+1}]:\n{chunk.get('content', '')[:500]}"
                for i, chunk in enumerate(chunks[:5])  # Top 5 chunks más relevantes
            ])
            
            # Prompt mejorado para detección
            prompt = f"""Eres un validador de precisión de respuestas. Tu tarea es verificar si la respuesta está fundamentada en las fuentes proporcionadas.

    FUENTES DISPONIBLES:
    {context}

    RESPUESTA A VALIDAR:
    {answer[:800]}

    INSTRUCCIONES:
    Analiza si la respuesta contiene:
    1. Información que NO aparece en las fuentes
    2. Conclusiones no justificadas por las fuentes
    3. Datos inventados o especulativos
    4. Nombres, fechas o cifras que no están en las fuentes

    CRITERIOS DE VALIDACIÓN:
    - Si la respuesta solo usa información de las fuentes: RESPONDE "NO"
    - Si la respuesta inventa información: RESPONDE "SI"
    - Si hay dudas menores pero la respuesta es mayormente correcta: RESPONDE "NO"

    IMPORTANTE: 
    - Es NORMAL que la respuesta reformule o sintetice la información de las fuentes
    - Solo marca como alucinación si hay información CLARAMENTE INVENTADA
    - Recomendaciones basadas en las fuentes son VÁLIDAS

    RESPUESTA (solo SI o NO):"""

            logger.info("   🔍 Analizando coherencia con fuentes...")
            
            response = self.openai_client.chat.completions.create(
                model=self.config.get_chat_model_config().deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=20
            )
            
            result = response.choices[0].message.content.strip().upper()
            
            # Parsear respuesta
            has_hallucination = "SI" in result or "SÍ" in result
            
            if has_hallucination:
                # Score alto si detecta alucinación
                score = 0.85
                logger.warning(f"   ⚠️  Respuesta del validador: '{result}' → Score: {score}")
            else:
                # Score bajo si está bien fundamentada
                score = 0.15
                logger.info(f"   ✅ Respuesta del validador: '{result}' → Score: {score}")
            
            return score
            
        except Exception as e:
            logger.error(f"⚠️  Error en detección de alucinación: {e}")
            # En caso de error, asumir que está bien (no bloquear por fallo técnico)
            return 0.2
    
    def _validate_html(self, answer: str) -> bool:
        """Valida que el HTML esté bien formado"""
        open_tags = re.findall(r'<(\w+)[^>]*>', answer)
        close_tags = re.findall(r'</(\w+)>', answer)
        
        self_closing = ['br', 'hr', 'img', 'input']
        open_tags = [tag for tag in open_tags if tag not in self_closing]
        
        return sorted(open_tags) == sorted(close_tags)
    
    def _sanitize_html(self, answer: str) -> str:
        """Sanitiza HTML malformado"""
        answer = re.sub(r'<(\w+)[^>]*>(?!.*</\1>)', '', answer)
        return answer


class GuardRailsManager:
    """Manager principal que coordina input y output guardrails CON LOGGING"""
    
    def __init__(self):
        self.input_guardrails = InputGuardRails()
        self.output_guardrails = OutputGuardRails()
        self.violation_log = []
        
        logger.info("🛡️  GuardRails Manager inicializado")
    
    def validate_input(self, query: str, user_id: str = "anonymous") -> Tuple[bool, Dict]:
        """Valida input del usuario"""
        try:
            result = self.input_guardrails.validate(query, user_id)
            
            if not result["is_safe"]:
                self._log_violation("input", query, result, user_id)
            
            return result["is_safe"], result
            
        except GuardRailsViolation as e:
            logger.critical(f"🚨 VIOLACIÓN CRÍTICA BLOQUEADA: {str(e)}")
            self._log_violation("input", query, {"error": str(e)}, user_id)
            return False, {"error": str(e), "is_safe": False}
    
    def validate_output(
        self, 
        answer: str, 
        query: str, 
        chunks_used: List[Dict],
        metadata: Dict
    ) -> Tuple[bool, Dict]:
        """Valida output generado"""
        result = self.output_guardrails.validate(answer, query, chunks_used, metadata)
        
        if not result["is_compliant"]:
            self._log_violation("output", answer, result, metadata.get("user_id", "unknown"))
        
        return result["is_compliant"], result
    
    def _log_violation(self, stage: str, content: str, result: Dict, user_id: str):
        """Registra violaciones para auditoría"""
        violation = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "user_id": user_id,
            "content_preview": content[:100],
            "result": result
        }
        self.violation_log.append(violation)
        
        logger.warning("="*60)
        logger.warning(f"📋 VIOLACIÓN REGISTRADA EN LOG")
        logger.warning(f"   Stage: {stage}")
        logger.warning(f"   User: {user_id}")
        logger.warning(f"   Time: {violation['timestamp']}")
        logger.warning("="*60)
    
    def get_violation_summary(self) -> Dict:
        """Retorna resumen de violaciones"""
        summary = {
            "total_violations": len(self.violation_log),
            "by_stage": {
                "input": len([v for v in self.violation_log if v["stage"] == "input"]),
                "output": len([v for v in self.violation_log if v["stage"] == "output"])
            },
            "recent": self.violation_log[-10:]
        }
        
        logger.info(f"📊 Resumen de violaciones: {summary['total_violations']} total")
        
        return summary


# Instancia global
guardrails_manager = GuardRailsManager()