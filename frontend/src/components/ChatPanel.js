import React, { useState, useEffect, useRef, useCallback } from 'react';
import MessageBubble from './MessageBubble';

export default function ChatPanel({
  useCase,
  userId,
  language,
  conversationId,
  onConversationCreated,
  onConversationUpdated,
}) {
  const [messages, setMessages]       = useState([]);
  const [input, setInput]             = useState('');
  const [loading, setLoading]         = useState(false);
  const [lastCost, setLastCost]       = useState(null);
  const [activeConvId, setActiveConvId] = useState(conversationId);
  const messagesEndRef                = useRef(null);
  const textareaRef                   = useRef(null);

  // Cargar mensajes de conversación existente
  useEffect(() => {
    setActiveConvId(conversationId);
    if (conversationId) {
      fetch(`/api/conversations/${conversationId}`)
        .then(r => r.json())
        .then(data => {
          if (data.messages) {
            setMessages(data.messages.map((m, i) => ({
              id: i,
              role: m.role,
              content: m.content,
            })));
          }
        })
        .catch(() => {});
    } else {
      setMessages([]);
    }
    setLastCost(null);
  }, [conversationId]);

  // Auto-scroll al fondo
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Auto-resize del textarea
  function handleInputChange(e) {
    setInput(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
    }
  }

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { id: Date.now(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setLoading(true);
    setLastCost(null);

    try {
      const form = new FormData();
      form.append('query', text);
      form.append('user_id', userId);
      form.append('use_case', useCase.id);
      form.append('language', language);
      if (activeConvId) form.append('conversation_id', activeConvId);

      const res = await fetch('/api/chat', { method: 'POST', body: form });
      const data = await res.json();

      if (!res.ok) {
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: 'error',
          content: data.error || 'Error desconocido del servidor.',
        }]);
        return;
      }

      const convId = data.conversation_id;

      // Si es conversación nueva, notificamos al padre
      if (!activeConvId && convId) {
        setActiveConvId(convId);
        onConversationCreated?.({
          id: convId,
          title: text.slice(0, 50) + (text.length > 50 ? '…' : ''),
          use_case: useCase.id,
          created_at: new Date().toISOString(),
        });
      }

      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.answer,
        chunks: data.chunks_used || [],
        meta: data.metadata || {},
      };
      setMessages(prev => [...prev, assistantMsg]);

      // Costo
      const cost = data.metadata?.cost;
      if (cost?.total_cost_usd != null) {
        setLastCost(`Costo estimado: $${cost.total_cost_usd.toFixed(6)}`);
      }

      // Notificar actualización al padre (para el sidebar)
      if (convId) {
        onConversationUpdated?.({
          id: convId,
          title: text.slice(0, 50),
          use_case: useCase.id,
        });
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 2,
        role: 'error',
        content: 'No se pudo conectar con el servidor. Comprueba que el backend está en ejecución.',
      }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, userId, useCase, language, activeConvId, onConversationCreated, onConversationUpdated]);

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="chat-panel">
      {/* Pantalla de bienvenida si no hay mensajes */}
      {!hasMessages && (
        <div className="chat-panel__welcome">
          <div className="chat-panel__welcome-icon">{useCase?.icon}</div>
          <h2 className="chat-panel__welcome-title">{useCase?.label}</h2>
          <p className="chat-panel__welcome-desc">{useCase?.description}</p>
        </div>
      )}

      {/* lista de mensajes */}
      {hasMessages && (
        <div className="chat-panel__messages">
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Indicador de carga */}
          {loading && (
            <div className="msg msg--assistant">
              <div className="msg__bubble">
                <div className="msg__typing">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Área de entrada */}
      <div className="chat-panel__input-area">
        <div className="chat-panel__input-row">
          <textarea
            ref={textareaRef}
            className="chat-panel__textarea"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={`Pregunta sobre ${useCase?.label}…`}
            rows={1}
            disabled={loading}
          />
          <button
            className="chat-panel__send-btn"
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            aria-label="Enviar"
          >
            ➤
          </button>
        </div>
        <div className="chat-panel__cost">{lastCost}</div>
        <p className="chat-panel__hint">Intro para enviar · Shift+Intro para nueva línea</p>
      </div>
    </div>
  );
}
