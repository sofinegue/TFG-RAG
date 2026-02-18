import { useState, useEffect, useMemo, useContext } from 'react';
import { AuthContext } from './Context';
import { API_BASE_URL } from '../config';
import AssistantManager from './AssistantManager';
import './Sidebar.css';

const Sidebar = () => {
  const {
    loggedUser, setLoggedUser,
    groupUser,
    selectedAssistant, setSelectedAssistant,
    stats, setStats,
    updateStats, setUpdateStats,
    assistants, setAssistants,
    setMessages,
    conversations, setConversations,
    currentConversationId, setCurrentConversationId,
    ragMode, setRagMode,
    welcomeBox, setWelcomeBox,
    loadingAssistants, setLoadingAssistants,
    isFiltering, setIsFiltering,
    showAssistantManager, setShowAssistantManager,
    enableWrite,
    gptMode,
  } = useContext(AuthContext);

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [files, setFiles] = useState([]);
  const [idLlamada, setIdLlamada] = useState(`upload_${new Date().toISOString().slice(0, 19).replace(/[-T:]/g, '')}`);
  const [equipo, setEquipo] = useState('default');
  const [idCaso, setIdCaso] = useState('default');
  const [getFormula, setGetFormula] = useState(false);

  const assistantInfo = useMemo(
    () => (selectedAssistant ? assistants[selectedAssistant] : null),
    [assistants, selectedAssistant]
  );

  // Load assistants on mount
  useEffect(() => { loadAssistants(); }, []);

  // Auto-select first allowed assistant
  useEffect(() => {
    if (!loadingAssistants && Object.keys(assistants).length > 0) {
      setIsFiltering(true);
      const filtered = Object.entries(assistants).filter(
        ([_, c]) => c.allowed_groups?.includes(groupUser)
      );
      setIsFiltering(false);
      if (filtered.length > 0) {
        setSelectedAssistant(filtered[0][0]);
      } else {
        setSelectedAssistant(null);
      }
    }
  }, [loadingAssistants, assistants]);

  // Load conversations
  useEffect(() => {
    if (!loggedUser) return;
    fetch(`${API_BASE_URL}/api/conversations?user_id=${loggedUser}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          const filtered = data.filter(conv => Object.keys(assistants).includes(conv.assistant_id));
          setConversations(filtered);
        } else {
          setConversations([]);
        }
      })
      .catch(() => setConversations([]));
  }, [loggedUser, assistants]);

  // Stats
  useEffect(() => {
    if (!currentConversationId || !updateStats) return;
    fetch(`${API_BASE_URL}/api/stats/${currentConversationId}`)
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error('Stats error:', err))
      .finally(() => setUpdateStats(false));
  }, [updateStats, currentConversationId]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownOpen && !e.target.closest('.assistant-select')) setDropdownOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [dropdownOpen]);

  const loadAssistants = async () => {
    setLoadingAssistants(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/assistants/config`);
      const data = await res.json();
      if (data.assistants && Object.keys(data.assistants).length > 0) {
        setAssistants(data.assistants);
        setSelectedAssistant(Object.keys(data.assistants)[0]);
      } else {
        setAssistants({});
      }
    } catch {
      // Fallback
      try {
        const res = await fetch(`${API_BASE_URL}/api/assistants`);
        const data = await res.json();
        if (data && Object.keys(data).length > 0) {
          setAssistants(data);
          setSelectedAssistant(Object.keys(data)[0]);
        }
      } catch {}
    } finally {
      setLoadingAssistants(false);
    }
  };

  const handleAssistantChange = async (key) => {
    if (!loggedUser || loggedUser.startsWith('temp_')) return;
    try {
      const formData = new FormData();
      formData.append('user_id', loggedUser);
      formData.append('assistant_key', key);
      const res = await fetch(`${API_BASE_URL}/api/update-assistant`, { method: 'POST', body: formData });
      const data = await res.json();
      if (data.success) {
        setSelectedAssistant(key);
        setCurrentConversationId(null);
        setMessages([]);
        setWelcomeBox(true);
        // Reload conversations
        const convRes = await fetch(`${API_BASE_URL}/api/conversations?user_id=${loggedUser}`);
        const convData = await convRes.json();
        setConversations(Array.isArray(convData) ? convData : []);
      }
    } catch (err) {
      console.error('Error changing assistant:', err);
    }
  };

  const updateAssistantBackendOnly = async (key) => {
    if (!loggedUser || loggedUser.startsWith('temp_')) return false;
    try {
      const formData = new FormData();
      formData.append('user_id', loggedUser);
      formData.append('assistant_key', key);
      const res = await fetch(`${API_BASE_URL}/api/update-assistant`, { method: 'POST', body: formData });
      const data = await res.json();
      if (data.success) { setSelectedAssistant(key); return true; }
      return false;
    } catch { return false; }
  };

  const createNewConversation = async () => {
    if (!loggedUser || loggedUser.startsWith('temp_')) return;
    try {
      const formData = new FormData();
      formData.append('user_id', loggedUser);
      formData.append('assistant_id', selectedAssistant || 'default');
      const res = await fetch(`${API_BASE_URL}/api/conversations/create`, { method: 'POST', body: formData });
      if (!res.ok) return;
      const data = await res.json();
      setCurrentConversationId(data.conversation_id);
      setMessages([]);
      setWelcomeBox(true);
      const convRes = await fetch(`${API_BASE_URL}/api/conversations?user_id=${loggedUser}`);
      const convData = await convRes.json();
      setConversations(Array.isArray(convData) ? convData : []);
    } catch (err) {
      console.error('Error creating conversation:', err);
    }
  };

  const handleDeleteConversation = async (id) => {
    if (!window.confirm('Delete this conversation?')) return;
    try {
      const formData = new FormData();
      formData.append('conversation_id', id);
      const res = await fetch(`${API_BASE_URL}/api/delete-conversation`, { method: 'POST', body: formData });
      const data = await res.json();
      if (data.message) {
        const updated = conversations.filter(c => c.id !== id);
        setConversations(updated);
        if (currentConversationId === id) {
          setCurrentConversationId(updated.length > 0 ? updated[updated.length - 1].id : null);
          setWelcomeBox(true);
        }
      }
    } catch (err) {
      console.error('Error deleting conversation:', err);
    }
  };

  const loadConversation = async (convId) => {
    setCurrentConversationId(convId);
    setWelcomeBox(false);
    try {
      const res = await fetch(`${API_BASE_URL}/api/conversations/${convId}`);
      const data = await res.json();
      if (data.conversation) {
        setMessages(data.conversation.messages || []);
        if (data.conversation.assistant_id && assistants[data.conversation.assistant_id]) {
          updateAssistantBackendOnly(data.conversation.assistant_id);
        }
      } else {
        setMessages([]);
      }
    } catch {
      setMessages([]);
    }
    setUpdateStats(true);
  };

  const filteredAssistants = Object.entries(assistants).filter(
    ([_, c]) => c.allowed_groups?.includes(groupUser) && !c.connected_to
  );

  return (
    <div className="sidebar-inner">
      {/* Mode toggle */}
      <div className="sb-section">
        <h3 className="sb-label">Mode</h3>
        <div className="mode-btns">
          <button
            className={ragMode === 'assistant' ? 'active' : ''}
            disabled={ragMode === 'assistant'}
            onClick={() => setRagMode('assistant')}
          >Assistants</button>
          <button
            className={ragMode === 'gpt' ? 'active' : ''}
            disabled={ragMode === 'gpt' || !gptMode}
            onClick={() => setRagMode('gpt')}
            title={!gptMode ? 'GPT mode is disabled' : ''}
          >GPT</button>
        </div>
      </div>

      {/* New chat */}
      <div className="sb-section">
        <button
          className="new-chat-btn"
          onClick={createNewConversation}
          disabled={welcomeBox || !enableWrite}
        >
          + New Chat
        </button>
      </div>

      {/* Assistant selector */}
      {ragMode === 'assistant' && (
        <div className="sb-section">
          <h3 className="sb-label">Assistant</h3>
          {loadingAssistants || isFiltering ? (
            <p className="sb-info">Loading assistants...</p>
          ) : filteredAssistants.length > 0 ? (
            <>
              <div className="assistant-select">
                <button className="select-trigger" onClick={() => setDropdownOpen(!dropdownOpen)}>
                  <span>{assistants[selectedAssistant]?.name || selectedAssistant}</span>
                  <span className="arrow">{dropdownOpen ? '▲' : '▼'}</span>
                </button>
                {dropdownOpen && (
                  <ul className="select-dropdown">
                    {filteredAssistants.map(([id, config]) => {
                      const subs = config.connected_agents || [];
                      return (
                        <li key={id}>
                          <div
                            className={`opt ${selectedAssistant === id ? 'selected' : ''}`}
                            onClick={() => { handleAssistantChange(id); setDropdownOpen(false); }}
                          >
                            {config.name || id}
                            {subs.length > 0 && <span className="badge">{subs.length}</span>}
                          </div>
                          {subs.length > 0 && (
                            <ul className="sub-list">
                              {subs.map(subKey => {
                                const sub = assistants[subKey];
                                if (!sub) return null;
                                return (
                                  <li
                                    key={subKey}
                                    className={`sub-opt ${selectedAssistant === subKey ? 'selected' : ''}`}
                                    onClick={(e) => { e.stopPropagation(); handleAssistantChange(subKey); setDropdownOpen(false); }}
                                  >
                                    ↳ {sub.name || subKey}
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              {assistantInfo && (
                <details className="assistant-details">
                  <summary>Assistant Info</summary>
                  <div className="details-content">
                    <p><strong>Name:</strong> {assistantInfo.name || 'N/A'}</p>
                    <p><strong>Description:</strong> {assistantInfo.description || 'N/A'}</p>
                    <p><strong>Model:</strong> {assistantInfo.deployment || 'N/A'}</p>
                    {assistantInfo.vector_store_id && <p><strong>Vector Store:</strong> {assistantInfo.vector_store_id}</p>}
                  </div>
                </details>
              )}
            </>
          ) : (
            <p className="sb-info sb-warn">No assistants available for your group</p>
          )}
        </div>
      )}

      {/* Conversation History */}
      <div className="sb-section sb-grow">
        <h3 className="sb-label">Conversations</h3>
        {loadingAssistants ? (
          <p className="sb-info">Loading...</p>
        ) : (
          <div className="conv-list">
            {conversations.length > 0 ? (
              [...conversations]
                .sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at))
                .map(conv => {
                  const title = (conv.messages?.length > 0)
                    ? conv.messages[0].content
                    : conv.title || 'New Conversation';
                  const isActive = conv.id === currentConversationId;
                  const date = conv.updated_at || conv.created_at;
                  const formatted = date
                    ? new Date(date).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
                    : '';

                  return (
                    <div key={conv.id} className={`conv-item ${isActive ? 'active' : ''}`}>
                      <button className="conv-btn" onClick={() => loadConversation(conv.id)}>
                        {formatted && <span className="conv-date">{formatted}</span>}
                        <span className="conv-title">{title}</span>
                      </button>
                      {!isActive && (
                        <button
                          className="conv-delete"
                          onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }}
                          title="Delete conversation"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  );
                })
            ) : (
              <p className="sb-info">No conversations yet</p>
            )}
          </div>
        )}
      </div>

      {/* Upload documents (GPT mode) */}
      {ragMode === 'gpt' && (
        <div className="sb-section">
          <details>
            <summary className="sb-label clickable">Upload Documents</summary>
            <form className="upload-form" onSubmit={(e) => {
              e.preventDefault();
              const fd = new FormData();
              fd.append('id_llamada', idLlamada);
              fd.append('equipo', equipo);
              fd.append('id_caso', idCaso);
              fd.append('userId', loggedUser);
              fd.append('get_formula', getFormula);
              files.forEach(f => fd.append('files', f));
              fetch(`${API_BASE_URL}/api/upload-documents`, { method: 'POST', body: fd })
                .then(r => r.json())
                .then(() => alert('Documents uploaded'))
                .catch(err => console.error('Upload error:', err));
            }}>
              <input type="text" placeholder="Call ID" value={idLlamada} onChange={e => setIdLlamada(e.target.value)} required />
              <input type="text" placeholder="Team" value={equipo} onChange={e => setEquipo(e.target.value)} required />
              <input type="text" placeholder="Case ID" value={idCaso} onChange={e => setIdCaso(e.target.value)} required />
              <label className="checkbox-label">
                <input type="checkbox" checked={getFormula} onChange={e => setGetFormula(e.target.checked)} />
                Get Formula
              </label>
              <input type="file" multiple accept=".pdf,.docx,.pptx,.txt" onChange={e => setFiles(Array.from(e.target.files))} />
              <button type="submit" className="upload-btn">Upload</button>
            </form>
          </details>
        </div>
      )}

      {/* Config */}
      <div className="sb-section">
        <h3 className="sb-label">Settings</h3>
        <button
          className="config-btn"
          disabled={ragMode !== 'assistant'}
          onClick={() => setShowAssistantManager(true)}
        >
          Manage Assistants
        </button>
      </div>

      {showAssistantManager && (
        <AssistantManager onClose={() => setShowAssistantManager(false)} />
      )}

      {/* Stats */}
      {stats && (
        <div className="sb-section">
          <details>
            <summary className="sb-label clickable">Statistics</summary>
            <div className="stats-panel">
              <p className="stats-caption">Pricing date: {stats.pricing_date}</p>
              <h4>Last Query</h4>
              <p>Model: {stats.last_query_models.join(', ')}</p>
              <p>Input: {stats.last_query_input} | Output: {stats.last_query_output}</p>
              <p>Tokens: {stats.last_query.metadata.usage.total_tokens}</p>
              <p>Time: {stats.last_query.metadata.total_time.toFixed(2)}s</p>

              <h4>Averages</h4>
              <p>Input: {stats.averages.avg_input.toFixed(0)} | Output: {stats.averages.avg_output.toFixed(0)}</p>
              <p>Cost: ${stats.averages.avg_cost.toFixed(6)} | Time: {stats.averages.avg_time.toFixed(2)}s</p>

              <h4>Totals</h4>
              <p>Queries: {stats.totals.queries} | Messages: {stats.totals.messages}</p>
              <p>Cost: ${stats.totals.total_cost.toFixed(6)} | Time: {stats.totals.total_time.toFixed(2)}s</p>
              <p>Models: {stats.totals.models_used.join(', ')}</p>
            </div>
          </details>
        </div>
      )}
    </div>
  );
};

export default Sidebar;
