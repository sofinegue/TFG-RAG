import json
import logging
from pathlib import Path

# Logger para errores
logger = logging.getLogger(__name__)

# Ruta al archivo de configuración
PRICING_FILE = Path("utils/pricing_config.json")

def get_default_pricing():
    """Precios por defecto si falla la carga del JSON"""
    return {
        "gpt-5-mini": {"input": 0.25, "input_cached": 0.025, "output": 2.00, "context": 1000000},
        "gpt-4o": {"input": 5.00, "input_cached": 2.50, "output": 20.00, "context": 128000},
        "gpt-4o-mini": {"input": 0.60, "input_cached": 0.30, "output": 2.40, "context": 128000},
    }

def load_model_pricing():
    """
    Carga precios desde pricing_config.json

    Returns:
        tuple: (dict de precios normalizados, fecha de actualización)
    """
    if not PRICING_FILE.exists():
        logger.warning("⚠️ pricing_config.json no encontrado, usando precios por defecto")
        return get_default_pricing(), "desconocido"

    try:
        with open(PRICING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        pricing = {}
        for model, prices in data.get("models", {}).items():
            normalized_name = model.lower().replace(".", "-")
            pricing[normalized_name] = prices

        last_updated = data.get("last_updated", "desconocido")
        return pricing, last_updated

    except Exception as e:
        logger.error(f"❌ Error cargando pricing_config.json: {e}")
        return get_default_pricing(), "desconocido"

def calculate_cost(model_name: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0, reasoning_tokens: int = 0, pricing_dict: dict = None) -> dict:
    """
    Calcula el costo de una llamada al modelo usando los precios dados

    Args:
        model_name: Nombre del modelo (ej: "gpt-5-mini-2025-08-07")
        input_tokens: Tokens de input
        output_tokens: Tokens de output
        cached_tokens: Tokens cacheados
        reasoning_tokens: Tokens de reasoning
        pricing_dict: Diccionario de precios cargado previamente

    Returns:
        dict con desglose de costos
    """
    if pricing_dict is None:
        pricing_dict, _ = load_model_pricing()

    model_key = model_name.lower().replace(".", "-")

    if model_key not in pricing_dict:
        parts = model_key.split('-')
        if len(parts) >= 3:
            model_key = '-'.join(parts[:3])  # gpt-5-mini

    if model_key not in pricing_dict:
        return {
            "input_cost": 0.0,
            "output_cost": 0.0,
            "cached_cost": 0.0,
            "reasoning_cost": 0.0,
            "total_cost": 0.0,
            "error": f"Modelo '{model_name}' no encontrado en pricing_config.json"
        }

    pricing = pricing_dict[model_key]

    input_cost = ((input_tokens - cached_tokens) / 1_000_000) * pricing.get("input", 0)
    cached_cost = (cached_tokens / 1_000_000) * pricing.get("input_cached", 0)
    output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0)
    reasoning_cost = (reasoning_tokens / 1_000_000) * pricing.get("output", 0)

    total_cost = input_cost + cached_cost + output_cost + reasoning_cost

    return {
        "input_cost": input_cost,
        "cached_cost": cached_cost,
        "output_cost": output_cost,
        "reasoning_cost": reasoning_cost,
        "total_cost": total_cost,
        "model": model_key,
        "pricing_source": "pricing_config.json"
    }