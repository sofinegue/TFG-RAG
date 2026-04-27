"""
GuardRails: validación de inputs y outputs del sistema RAG.
Adaptado de src_rag para usar imports absolutos (src.*).
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from openai import AzureOpenAI
from src.config import config

logger = logging.getLogger("guardrails")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | guardrails | %(message)s", "%H:%M:%S"))
logger.addHandler(_handler)


class GuardRailsViolation(Exception):
    """Se lanza cuando el input/output viola las políticas de uso."""
    pass


class InputGuardRails:
    def __init__(self):
        chat_cfg = config.get_chat_model_config()
        self.openai_client = AzureOpenAI(
            api_key=chat_cfg.api_key,
            api_version=chat_cfg.api_version,
            azure_endpoint=chat_cfg.api_base,
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
            "password", "token", "secret", "credential",
        ]

    def validate(self, query: str, user_id: str = "anonymous") -> Dict:
        result = {
            "is_safe": True,
            "violations": [],
            "sanitized_query": query,
            "risk_level": "low",
            "timestamp": datetime.now().isoformat(),
        }

        if not query or not query.strip():
            result["is_safe"] = False
            result["violations"].append("empty_query")
            return result

        if len(query) > 5000:
            result["is_safe"] = False
            result["violations"].append("excessive_length")
            result["risk_level"] = "medium"
            raise GuardRailsViolation("Query demasiado larga (> 5000 chars)")

        injection = self._detect_injection(query)
        if injection:
            result["is_safe"] = False
            result["violations"].append("prompt_injection")
            result["risk_level"] = "high"
            raise GuardRailsViolation(f"Prompt injection detectado: {injection}")

        suspicious = self._check_suspicious_keywords(query)
        if suspicious:
            result["violations"].append("suspicious_keywords")
            result["risk_level"] = "medium"

        if config.enable_content_moderation:
            mod = self._moderate_content(query)
            if mod["flagged"]:
                result["is_safe"] = False
                result["violations"].append("content_moderation")
                result["risk_level"] = "high"
                raise GuardRailsViolation(f"Contenido inapropiado: {mod['categories']}")

        result["sanitized_query"] = self._sanitize_query(query)
        return result

    def _detect_injection(self, query: str) -> Optional[str]:
        ql = query.lower()
        for p in self.injection_patterns:
            m = re.search(p, ql, re.IGNORECASE)
            if m:
                return m.group(0)
        return None

    def _check_suspicious_keywords(self, query: str) -> List[str]:
        ql = query.lower()
        return [kw for kw in self.suspicious_keywords if kw in ql]

    def _moderate_content(self, query: str) -> Dict:
        try:
            res = self.openai_client.moderations.create(input=query)
            r = res.results[0]
            return {
                "flagged": r.flagged,
                "categories": [c for c, f in r.categories.model_dump().items() if f],
            }
        except Exception:
            return {"flagged": False, "categories": []}

    def _sanitize_query(self, query: str) -> str:
        sanitized = re.sub(r"<[^>]+>", "", query)
        sanitized = re.sub(r"[\x00-\x1F\x7F]", "", sanitized)
        return re.sub(r"\s+", " ", sanitized).strip()


class OutputGuardRails:
    def __init__(self):
        chat_cfg = config.get_chat_model_config()
        self.openai_client = AzureOpenAI(
            api_key=chat_cfg.api_key,
            api_version=chat_cfg.api_version,
            azure_endpoint=chat_cfg.api_base,
        )
        self.requires_disclaimer = [
            "médico", "salud", "diagnóstico", "tratamiento",
            "legal", "abogado", "ley", "contrato",
            "financiero", "inversión", "impuestos",
        ]

    def validate(self, answer: str, query: str, chunks_used: List[Dict], metadata: Dict) -> Dict:
        result = {
            "is_compliant": True,
            "issues": [],
            "enhanced_answer": answer,
            "risk_level": "low",
            "timestamp": datetime.now().isoformat(),
        }

        if len(answer) < 10:
            result["is_compliant"] = False
            result["issues"].append("too_short")
            result["enhanced_answer"] = "Lo siento, no pude generar una respuesta adecuada."
            return result

        needs_disclaimer = self._check_disclaimer_needed(answer)
        if needs_disclaimer:
            result["issues"].append("missing_disclaimer")
            result["enhanced_answer"] = self._add_disclaimer(answer, needs_disclaimer)

        if chunks_used and config.enable_hallucination_check:
            score = self._detect_hallucination(answer, chunks_used)
            result["hallucination_score"] = score
            if score > 0.7:
                result["issues"].append("possible_hallucination")
                result["risk_level"] = "medium"

        if len(answer) > config.max_answer_chars * 1.2:
            result["issues"].append("excessive_length")
            result["enhanced_answer"] = answer[: config.max_answer_chars] + "..."

        if not self._validate_html(answer):
            result["issues"].append("invalid_html")
            result["enhanced_answer"] = self._sanitize_html(result["enhanced_answer"])

        return result

    def _check_disclaimer_needed(self, answer: str) -> List[str]:
        al = answer.lower()
        return [kw for kw in self.requires_disclaimer if kw in al]

    def _add_disclaimer(self, answer: str, categories: List[str]) -> str:
        disclaimers = {
            "médico":    "\n\n⚠️ Esta información es orientativa. Consulta con un profesional de la salud.",
            "legal":     "\n\n⚠️ Esta información es general. Para asesoría legal, consulta con un abogado.",
            "financiero":"\n\n⚠️ Esta información no constituye asesoría financiera.",
        }
        cat = categories[0] if categories else None
        for key, disc in disclaimers.items():
            if cat and key in cat:
                return answer + disc
        return answer

    def _detect_hallucination(self, answer: str, chunks: List[Dict]) -> float:
        try:
            context = "\n\n".join(
                f"[Fuente {i+1}]:\n{c.get('content','')[:500]}"
                for i, c in enumerate(chunks[:5])
            )
            prompt = f"""Verifica si la siguiente RESPUESTA está basada solo en las FUENTES.

FUENTES:
{context}

RESPUESTA:
{answer[:800]}

¿La respuesta inventa información que NO está en las fuentes? Responde solo SÍ o NO."""

            res = self.openai_client.chat.completions.create(
                model=config.get_chat_model_config().deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            text = res.choices[0].message.content.strip().upper()
            return 0.85 if ("SÍ" in text or "SI" in text) else 0.15
        except Exception:
            return 0.2

    def _validate_html(self, answer: str) -> bool:
        open_tags  = re.findall(r"<(\w+)[^>]*>", answer)
        close_tags = re.findall(r"</(\w+)>", answer)
        self_closing = {"br", "hr", "img", "input"}
        open_tags = [t for t in open_tags if t not in self_closing]
        return sorted(open_tags) == sorted(close_tags)

    def _sanitize_html(self, answer: str) -> str:
        return re.sub(r"<(\w+)[^>]*>(?!.*</\1>)", "", answer)


class GuardRailsManager:
    def __init__(self):
        self.input_guardrails  = InputGuardRails()
        self.output_guardrails = OutputGuardRails()
        self.violation_log: List[Dict] = []

    def validate_input(self, query: str, user_id: str = "anonymous") -> Tuple[bool, Dict]:
        try:
            result = self.input_guardrails.validate(query, user_id)
            if not result["is_safe"]:
                self._log_violation("input", query, result, user_id)
            return result["is_safe"], result
        except GuardRailsViolation as e:
            self._log_violation("input", query, {"error": str(e)}, user_id)
            return False, {"is_safe": False, "error": str(e), "violations": ["guardrails_violation"]}

    def validate_output(
        self, answer: str, query: str, chunks_used: List[Dict], metadata: Dict
    ) -> Tuple[bool, Dict]:
        result = self.output_guardrails.validate(answer, query, chunks_used, metadata)
        if not result["is_compliant"]:
            self._log_violation("output", answer, result, metadata.get("user_id", "unknown"))
        return result["is_compliant"], result

    def _log_violation(self, stage: str, content: str, result: Dict, user_id: str):
        self.violation_log.append({
            "timestamp":       datetime.now().isoformat(),
            "stage":           stage,
            "user_id":         user_id,
            "content_preview": content[:100],
            "result":          result,
        })


guardrails_manager = GuardRailsManager()
