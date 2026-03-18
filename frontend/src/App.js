import React, { useState, useEffect } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import UseCaseSelector from './components/UseCaseSelector';

const USE_CASE_DEFAULTS = [
  { id: 'cvs',  label: 'CVs / Talento',  description: 'Búsqueda en currículums', icon: '👤' },
  { id: 'eu',   label: 'Legislación UE', description: 'Documentos de la Unión Europea', icon: '🇪🇺' },
  { id: 'wiki', label: 'Wikipedia',       description: 'Conocimiento general enciclopédico', icon: '📖' },
];

function generateUserId() {
  const stored = localStorage.getItem('rag_user_id');
  if (stored) return stored;
  const id = 'user_' + Math.random().toString(36).slice(2, 11);
  localStorage.setItem('rag_user_id', id);
  return id;
}

export default function App() {
  const [useCases, setUseCases]         = useState(USE_CASE_DEFAULTS);
  const [activeCase, setActiveCase]     = useState('cvs');
  const [userId]                        = useState(generateUserId);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId]   = useState(null);
  const [sidebarOpen, setSidebarOpen]     = useState(true);

  // Cargar casos de uso del backend
  useEffect(() => {
    fetch('/api/use-cases')
      .then(r => r.json())
      .then(data => {
        if (data.use_cases?.length) setUseCases(data.use_cases);
      })
      .catch(() => {/* usa defaults */});
  }, []);

  // Cargar historial de conversaciones
  useEffect(() => {
    fetch(`/api/conversations?user_id=${userId}`)
      .then(r => r.json())
      .then(data => {
        if (data.conversations) setConversations(data.conversations);
      })
      .catch(() => {});
  }, [userId]);

  function handleNewConversation() {
    setActiveConvId(null);
  }

  function handleSelectConversation(convId) {
    setActiveConvId(convId);
  }

  function handleConversationCreated(conv) {
    setActiveConvId(conv.id);
    setConversations(prev => [conv, ...prev.filter(c => c.id !== conv.id)]);
  }

  function handleConversationUpdated(conv) {
    setConversations(prev =>
      prev.map(c => (c.id === conv.id ? conv : c))
    );
  }

  function handleDeleteConversation(convId) {
    fetch(`/api/conversations/${convId}`, { method: 'DELETE' })
      .then(() => {
        setConversations(prev => prev.filter(c => c.id !== convId));
        if (activeConvId === convId) setActiveConvId(null);
      })
      .catch(() => {});
  }

  const activeUseCase = useCases.find(uc => uc.id === activeCase) || useCases[0];

  return (
    <div className={`app ${sidebarOpen ? 'app--sidebar-open' : ''}`}>
      {/* Cabecera */}
      <header className="app-header">
        <button
          className="app-header__menu-btn"
          onClick={() => setSidebarOpen(o => !o)}
          aria-label="Alternar panel lateral"
        >
          ☰
        </button>
        <h1 className="app-header__title">RAG Assistant</h1>
        <UseCaseSelector
          useCases={useCases}
          activeCase={activeCase}
          onChange={(id) => { setActiveCase(id); setActiveConvId(null); }}
        />
      </header>

      <div className="app-body">
        {/* Sidebar con historial */}
        <Sidebar
          open={sidebarOpen}
          conversations={conversations.filter(c => c.use_case === activeCase)}
          activeConvId={activeConvId}
          onNew={handleNewConversation}
          onSelect={handleSelectConversation}
          onDelete={handleDeleteConversation}
          useCase={activeUseCase}
        />

        {/* Panel de chat */}
        <ChatPanel
          key={`${activeCase}-${activeConvId}`}
          useCase={activeUseCase}
          userId={userId}
          conversationId={activeConvId}
          onConversationCreated={handleConversationCreated}
          onConversationUpdated={handleConversationUpdated}
        />
      </div>
    </div>
  );
}
