import React from 'react';

export default function UseCaseSelector({ useCases, activeCase, onChange }) {
  return (
    <nav className="use-case-selector" aria-label="Selector de caso de uso">
      {useCases.map(uc => (
        <button
          key={uc.id}
          className={`use-case-selector__tab${uc.id === activeCase ? ' use-case-selector__tab--active' : ''}`}
          onClick={() => onChange(uc.id)}
          title={uc.description}
        >
          <span className="use-case-selector__icon">{uc.icon}</span>
          <span>{uc.label}</span>
        </button>
      ))}
    </nav>
  );
}
