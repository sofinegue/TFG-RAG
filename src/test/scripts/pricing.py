"""
pricing.py
==========
Precios por modelo para calcular el coste ($) de los tests del TFG.
Fuente de precios: tabla oficial de OpenAI / Azure OpenAI (proporcionada).
Precios expresados por **1 M de tokens** (USD).
"""
from __future__ import annotations
# ---------------------------------------------------------------------------
# Tabla de precios (modelo/deployment → (precio_input, precio_output) por 1M tok)
# ---------------------------------------------------------------------------
# Las claves se normalizan a minúsculas en `token_cost_usd()`.
# Se admite tanto el nombre de modelo genérico como el nombre de deployment
# de Azure (que puede tener un sufijo, ej. "gpt-5.1-2").
_PRICING: dict[str, tuple[float, float]] = {
    # --- gpt-5 series (short context, tabla proporcionada) ---
    "gpt-5-nano":   (0.05,   0.40),
    "gpt-5-mini":   (0.25,   2.00),
    "gpt-5":        (1.25,  10.00),
    "gpt-5.1":      (1.25,  10.00),
    "gpt-5.1-2":    (1.25,  10.00),   # alias de deployment Azure
    "gpt-5.2":      (1.75,  14.00),
    "gpt-5.2-pro":  (21.00, 168.00),
    "gpt-5.4-nano": (0.20,   1.25),
    "gpt-5.4-mini": (0.75,   4.50),
    "gpt-5.4":      (2.50,  15.00),
    "gpt-5.4-pro":  (30.00, 180.00),
    "gpt-5.5":      (5.00,  30.00),
    "gpt-5.5-pro":  (30.00, 180.00),
    # --- Embeddings (solo input; sin tokens de salida) ---
    "ada-002":                (0.10, 0.00),
    "text-embedding-ada-002": (0.10, 0.00),
    # --- Legacy (no en la tabla; precio público de OpenAI) ---
    "gpt-4.1":      (2.00,   8.00),
    "gpt-4o":       (2.50,  10.00),
    "gpt-4o-mini":  (0.15,   0.60),
}
def token_cost_usd(model: str, tokens_in: int, tokens_out: int = 0) -> float:
    """Calcula el coste en USD para una llamada con `tokens_in` y `tokens_out`.
    El modelo puede ser el nombre genérico ("gpt-5-mini") o el nombre del
    deployment de Azure ("gpt-5.1-2"). Si no se encuentra en la tabla devuelve
    0.0 sin lanzar excepción.
    Parameters
    ----------
    model:
        Nombre del modelo o deployment (case-insensitive).
    tokens_in:
        Tokens de entrada (prompt_tokens en la API).
    tokens_out:
        Tokens de salida (completion_tokens). 0 para embeddings.
    Returns
    -------
    float
        Coste en dólares (USD), redondeado a 8 decimales.
    """
    key = (model or "").lower().strip()
    price_in, price_out = _PRICING.get(key, (0.0, 0.0))
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 8)
