import React from 'react';
import './UseCaseSelector.css';

export default function UseCaseSelector({ useCases, activeCase, onChange }) {
  if (!useCases.length) return null;

  return (
    <nav className="use-case-selector">
      {useCases.map(uc => (
        <button
          key={uc.id}
          className={`use-case-btn ${uc.id === activeCase ? 'use-case-btn--active' : ''}`}
          onClick={() => onChange(uc.id)}
          title={uc.description}
        >
          <span className="use-case-btn__icon">{uc.icon}</span>
          <span className="use-case-btn__label">{uc.label}</span>
        </button>
      ))}
    </nav>
  );
}
