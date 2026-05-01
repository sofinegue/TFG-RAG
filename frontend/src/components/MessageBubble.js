import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MessageBubble({ message }) {
  const [chunksOpen, setChunksOpen] = useState(false);

  if (message.role === 'error') {
    return (
      <div className="msg msg--assistant">
        <div className="msg__error">{message.content}</div>
      </div>
    );
  }

  const isUser = message.role === 'user';
  const chunks = message.chunks || [];

  return (
    <div className={`msg msg--${isUser ? 'user' : 'assistant'}`}>
      <div className="msg__bubble">
        {isUser ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        )}
      </div>

      {/* Fragmentos de contexto (solo en mensajes del asistente) */}
      {!isUser && chunks.length > 0 && (
        <div className="msg__chunks">
          <button
            className="msg__chunks-toggle"
            onClick={() => setChunksOpen(o => !o)}
          >
            {chunksOpen ? '▾' : '▸'} {chunks.length} fuente{chunks.length !== 1 ? 's' : ''} utilizadas
          </button>
          {chunksOpen && (
            <div className="msg__chunks-list">
              {chunks.map((chunk, i) => (
                <div key={i} className="msg__chunk-item">
                  {chunk.source && <strong>{chunk.source}</strong>}
                  {chunk.score != null && (
                    <span style={{ marginLeft: 8, opacity: 0.7 }}>
                      score: {chunk.score.toFixed(3)}
                    </span>
                  )}
                  {chunk.content && (
                    <p style={{ margin: '4px 0 0', opacity: 0.85 }}>
                      {chunk.content.slice(0, 200)}{chunk.content.length > 200 ? '…' : ''}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
