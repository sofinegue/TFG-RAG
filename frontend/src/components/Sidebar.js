import React from 'react';

export default function Sidebar({
  open,
  conversations,
  activeConvId,
  onNew,
  onSelect,
  onDelete,
  useCase,
}) {
  return (
    <aside className="sidebar" aria-label="Historial de conversaciones">
      <div className="sidebar__header">
        <span className="sidebar__use-case-icon">{useCase?.icon}</span>
        <span className="sidebar__use-case-label">{useCase?.label}</span>
        <button className="sidebar__new-btn" onClick={onNew}>
          + Nueva
        </button>
      </div>

      <div className="sidebar__list">
        {conversations.length === 0 ? (
          <p className="sidebar__empty">Sin conversaciones aún</p>
        ) : (
          conversations.map(conv => (
            <div
              key={conv.id}
              className={`sidebar__item${conv.id === activeConvId ? ' sidebar__item--active' : ''}`}
              onClick={() => onSelect(conv.id)}
              role="button"
              tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && onSelect(conv.id)}
            >
              <span className="sidebar__item-title">
                {conv.title || 'Conversación'}
              </span>
              <button
                className="sidebar__item-delete"
                onClick={e => { e.stopPropagation(); onDelete(conv.id); }}
                aria-label="Eliminar conversación"
                title="Eliminar"
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
