import React from 'react';

export default function LanguageSelector({ languages, activeLanguage, onChange }) {
  return (
    <div className="language-selector">
      <span className="language-selector__icon">🌐</span>
      <select
        className="language-selector__select"
        value={activeLanguage}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Selector de idioma"
      >
        {languages.map(lang => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </div>
  );
}
