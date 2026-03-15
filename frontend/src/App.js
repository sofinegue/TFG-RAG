import React, { useState, useEffect } from 'react';
import './App.css';
import UseCaseSelector from './components/UseCaseSelector';
import ChatPanel from './components/ChatPanel';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function App() {
  const [useCases, setUseCases]   = useState([]);
  const [activeCase, setActiveCase] = useState('cvs');
  const [userId]    = useState(() => `user_${Math.random().toString(36).slice(2, 9)}`);

  useEffect(() => {
    fetch(`${API_BASE}/api/use-cases`)
      .then(r => r.json())
      .then(data => {
        if (data.use_cases?.length) {
          setUseCases(data.use_cases);
          setActiveCase(data.use_cases[0].id);
        }
      })
      .catch(() => {
        // Defaults si el backend no está disponible
        setUseCases([
          { id: 'cvs',  label: 'CVs / Talento',    description: 'Búsqueda en currículums',              icon: '👤' },
          { id: 'eu',   label: 'Legislación UE',    description: 'Documentos de la Unión Europea',       icon: '🇪🇺' },
          { id: 'wiki', label: 'Wikipedia',          description: 'Conocimiento general enciclopédico',   icon: '📖' },
        ]);
      });
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__logo">🔍</span>
          <span className="app-header__title">RAG Assistant</span>
        </div>
        <UseCaseSelector
          useCases={useCases}
          activeCase={activeCase}
          onChange={setActiveCase}
        />
      </header>

      <main className="app-main">
        {useCases.map(uc => (
          <ChatPanel
            key={uc.id}
            useCase={uc}
            userId={userId}
            apiBase={API_BASE}
            visible={uc.id === activeCase}
          />
        ))}
      </main>
    </div>
  );
}
