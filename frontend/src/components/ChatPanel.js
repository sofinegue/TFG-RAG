import React, { useState, useRef, useEffect, useCallback } from 'react';
import './ChatPanel.css';

/* ── Helpers ──────────────────────────────────────────────────── */
function scrollToBottom(ref) {
  if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
}

/* ── Welcome messages per use case ───────────────────────────── */
const WELCOME = {
  cvs:  'Hola 👋 Puedo buscarte candidatos en nuestra base de CVs. Por ejemplo: "¿Quién tiene experiencia en Azure Data Factory?"',
  eu:   'Hola 👋 Soy tu experto en legislación de la Unión Europea. Pregúntame sobre directivas, reglamentos o acuerdos. Por ejemplo: "¿Qué dice el RGPD sobre el derecho al olvido?"',
  wiki: 'Hola 👋 Puedo responder preguntas de conocimiento general usando artículos de Wikipedia. Por ejemplo: "¿Qué es la inteligencia artificial?"',
};

/* ── Message bubble ───────────────────────────────────────────── */
function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`bubble-row ${isUser ? 'bubble-row--user' : 'bubble-row--assistant'}`}>
      {!isUser && <div className="bubble-avatar">🤖</div>}
      <div
        className={`bubble ${isUser ? 'bubble--user' : 'bubble--assistant'}`}
        dangerouslySetInnerHTML={isUser ? undefined : { __html: msg.content }}
      >
        {isUser ? msg.content : undefined}
      </div>
      {isUser && <div className="bubble-avatar bubble-avatar--user">👤</div>}
    </div>
  );
}

/* ── Sources panel (collapsed by default) ─────────────────────── */
function SourcesPanel({ chunks }) {
  const [open, setOpen] = useState(false);
  if (!chunks?.length) return null;
  return (
    <div className="sources">
      <button className="sources__toggle" onClick={() => setOpen(o => !o)}>
        📎 {chunks.length} fuentes {open ? '▲' : '▼'}
      </button>
      {open && (
        <ul className="sources__list">
          {chunks.map((c, i) => (
            <li key={i} className="sources__item">
              <strong>{c.doc_title || c.title || `Fuente ${i + 1}`}</strong>
              {c.pages && <span className="sources__pages"> · pág. {c.pages}</span>}
              {c.content && (
                <p className="sources__preview">{c.content.slice(0, 180)}…</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ── Main ChatPanel ───────────────────────────────────────────── */
export default function ChatPanel({ useCase, userId, apiBase, visible }) {
  const [messages, setMessages]   = useState([
    { role: 'assistant', content: WELCOME[useCase.id] || '¡Hola! ¿En qué puedo ayudarte?' },
  ]);
  const [input,    setInput]      = useState('');
  const [loading,  setLoading]    = useState(false);
  const [convId,   setConvId]     = useState(null);
  const [lastChunks, setLastChunks] = useState([]);
  const [error,    setError]      = useState(null);

  const listRef    = useRef(null);
  const inputRef   = useRef(null);

  // Auto-scroll al recibir mensajes nuevos
  useEffect(() => { scrollToBottom(listRef); }, [messages]);

  // Foco al activar el panel
  useEffect(() => {
    if (visible && inputRef.current) inputRef.current.focus();
  }, [visible]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput('');
    setError(null);
    setLastChunks([]);
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);

    try {
      const form = new FormData();
      form.append('query',    text);
      form.append('user_id',  userId);
      form.append('use_case', useCase.id);
      form.append('rag_mode', 'gpt');
      if (convId) form.append('conversation_id', convId);

      const res = await fetch(`${apiBase}/api/chat`, { method: 'POST', body: form });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || `Error ${res.status}`);
      }

      if (data.conversation_id && !convId) setConvId(data.conversation_id);
      if (data.chunks_used?.length)         setLastChunks(data.chunks_used);

      setMessages(prev => [...prev, { role: 'assistant', content: data.answer }]);
    } catch (e) {
      setError(e.message || 'Error desconocido');
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `<p style="color:#d32f2f">❌ ${e.message}</p>` },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, convId, userId, useCase.id, apiBase]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([
      { role: 'assistant', content: WELCOME[useCase.id] || '¡Hola!' },
    ]);
    setConvId(null);
    setLastChunks([]);
    setError(null);
  };

  if (!visible) return null;

  return (
    <div className="chat-panel">
      {/* Toolbar */}
      <div className="chat-panel__toolbar">
        <span className="chat-panel__case-label">
          {useCase.icon} {useCase.label}
        </span>
        <button className="chat-panel__clear-btn" onClick={clearChat} title="Nueva conversación">
          🗑️ Nueva
        </button>
      </div>

      {/* Message list */}
      <div className="chat-panel__messages" ref={listRef}>
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {loading && (
          <div className="bubble-row bubble-row--assistant">
            <div className="bubble-avatar">🤖</div>
            <div className="bubble bubble--assistant bubble--loading">
              <span className="dot-flashing" />
            </div>
          </div>
        )}
      </div>

      {/* Sources */}
      {lastChunks.length > 0 && <SourcesPanel chunks={lastChunks} />}

      {/* Input bar */}
      <div className="chat-panel__input-bar">
        <textarea
          ref={inputRef}
          className="chat-panel__textarea"
          placeholder={`Pregunta sobre ${useCase.label}…`}
          value={input}
          rows={1}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          className="chat-panel__send-btn"
          onClick={sendMessage}
          disabled={loading || !input.trim()}
        >
          {loading ? '⏳' : '➤'}
        </button>
      </div>

      {error && <p className="chat-panel__error">{error}</p>}
    </div>
  );
}
