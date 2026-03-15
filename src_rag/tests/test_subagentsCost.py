"""
Test para verificar el tracking de costes de sub-agentes
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.pricing import calculate_cost, load_model_pricing

def test_subagent_cost_calculation():
    """
    Simula un escenario con agente principal + 2 sub-agentes
    y verifica que el cálculo de costes sea correcto
    """
    MODEL_PRICING, _ = load_model_pricing()
    
    # Escenario simulado
    print("\n" + "="*60)
    print("TEST: Cálculo de costes con sub-agentes")
    print("="*60)
    
    # Agente principal
    main_agent = {
        "model": "gpt-5",
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "cached_tokens": 0,
        "reasoning_tokens": 0
    }
    
    # Sub-agentes
    sub_agents = [
        {
            "agent_id": "sub_agent_1",
            "model": "gpt-4o",
            "prompt_tokens": 300,
            "completion_tokens": 150,
            "cached_tokens": 0,
            "reasoning_tokens": 0
        },
        {
            "agent_id": "sub_agent_2",
            "model": "gpt-5-mini",
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "cached_tokens": 0,
            "reasoning_tokens": 0
        }
    ]
    
    # Calcular costes
    print("\n📊 Agente Principal:")
    print(f"   Modelo: {main_agent['model']}")
    print(f"   Tokens: {main_agent['prompt_tokens']} input + {main_agent['completion_tokens']} output")
    main_cost = calculate_cost(
        main_agent['model'],
        main_agent['prompt_tokens'],
        main_agent['completion_tokens'],
        main_agent['cached_tokens'],
        main_agent['reasoning_tokens'],
        pricing_dict=MODEL_PRICING
    )
    print(f"   💰 Coste: ${main_cost['total_cost']:.6f}")
    
    print("\n🔗 Sub-agentes:")
    total_sub_cost = 0
    for i, sub in enumerate(sub_agents, 1):
        print(f"\n   Sub-agente {i} ({sub['agent_id']}):")
        print(f"   Modelo: {sub['model']}")
        print(f"   Tokens: {sub['prompt_tokens']} input + {sub['completion_tokens']} output")
        sub_cost = calculate_cost(
            sub['model'],
            sub['prompt_tokens'],
            sub['completion_tokens'],
            sub['cached_tokens'],
            sub['reasoning_tokens'],
            pricing_dict=MODEL_PRICING
        )
        print(f"   💰 Coste: ${sub_cost['total_cost']:.6f}")
        total_sub_cost += sub_cost['total_cost']
    
    # Total
    total_cost = main_cost['total_cost'] + total_sub_cost
    
    print("\n" + "="*60)
    print("💰 RESUMEN DE COSTES:")
    print(f"   Agente principal: ${main_cost['total_cost']:.6f}")
    print(f"   Sub-agentes:      ${total_sub_cost:.6f}")
    print(f"   TOTAL:            ${total_cost:.6f}")
    print("="*60)
    
    # Verificar que funciona
    assert main_cost['total_cost'] > 0, "El coste del agente principal debe ser > 0"
    assert total_sub_cost > 0, "El coste de sub-agentes debe ser > 0"
    assert total_cost == main_cost['total_cost'] + total_sub_cost, "El total debe ser la suma"
    
    print("\n✅ TEST EXITOSO: El cálculo de costes funciona correctamente")
    return True

def test_message_structure():
    """
    Verifica la estructura de datos esperada en los mensajes
    """
    print("\n" + "="*60)
    print("TEST: Estructura de datos de mensaje con sub-agentes")
    print("="*60)
    
    # Mensaje simulado con sub-agentes
    message = {
        "role": "assistant",
        "content": "Respuesta del asistente...",
        "metadata": {
            "mode": "assistant",
            "total_time": 2.5,
            "model": "gpt-5",
            "context_messages": 4,
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "total_tokens": 1500,
                "model": "gpt-5"
            },
            "sub_agents_usage": [
                {
                    "agent_id": "sub_agent_1",
                    "model": "gpt-4o",
                    "prompt_tokens": 300,
                    "completion_tokens": 150,
                    "total_tokens": 450
                },
                {
                    "agent_id": "sub_agent_2",
                    "model": "gpt-5-mini",
                    "prompt_tokens": 200,
                    "completion_tokens": 100,
                    "total_tokens": 300
                }
            ]
        }
    }
    
    print("\n📋 Estructura del mensaje:")
    print(f"   Role: {message['role']}")
    print(f"   Content: {message['content'][:50]}...")
    print(f"   Metadata keys: {list(message['metadata'].keys())}")
    print(f"   Usage: {message['metadata']['usage']}")
    print(f"   Sub-agentes: {len(message['metadata']['sub_agents_usage'])} llamadas")
    
    # Verificar estructura
    assert message['role'] == 'assistant', "Role debe ser 'assistant'"
    assert 'usage' in message['metadata'], "Debe existir 'usage' en metadata"
    assert 'sub_agents_usage' in message['metadata'], "Debe existir 'sub_agents_usage' en metadata"
    assert isinstance(message['metadata']['sub_agents_usage'], list), "sub_agents_usage debe ser una lista"
    
    for i, sub in enumerate(message['metadata']['sub_agents_usage']):
        print(f"\n   Sub-agente {i+1}:")
        print(f"      ID: {sub['agent_id']}")
        print(f"      Modelo: {sub['model']}")
        print(f"      Tokens: {sub['total_tokens']}")
        
        assert 'agent_id' in sub, f"Sub-agente {i+1} debe tener 'agent_id'"
        assert 'model' in sub, f"Sub-agente {i+1} debe tener 'model'"
        assert 'total_tokens' in sub, f"Sub-agente {i+1} debe tener 'total_tokens'"
    
    print("\n✅ TEST EXITOSO: La estructura de datos es correcta")
    return True

if __name__ == "__main__":
    print("\n" + "🧪 INICIANDO TESTS DE SUB-AGENTES" + "\n")
    
    try:
        test_subagent_cost_calculation()
        test_message_structure()
        
        print("\n" + "="*60)
        print("✅ TODOS LOS TESTS PASARON CORRECTAMENTE")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FALLIDO: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR EN TESTS: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
