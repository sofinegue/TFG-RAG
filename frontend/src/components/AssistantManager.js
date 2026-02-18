import { useState, useEffect, useContext, useRef } from 'react';
import { AuthContext } from './Context';
import { API_BASE_URL } from '../config';
import './AssistantManager.css';

const AssistantManager = ({ onClose }) => {
  const {
    groupUser,
    assistants, setAssistants,
    setStats,
    setMessages,
    setCurrentConversationId,
    setWelcomeBox,
  } = useContext(AuthContext);

  const formRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [createMode, setCreateMode] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [selectedKey, setSelectedKey] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [availableGroups, setAvailableGroups] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [searchTab, setSearchTab] = useState('file_search');
  const [searchIndexes, setSearchIndexes] = useState([]);
  const [vectorStores, setVectorStores] = useState([]);
  const [dragActive, setDragActive] = useState(false);

  const [formData, setFormData] = useState({
    name: '', description: '', endpoint: '', api_type: 'azure_ai_projects',
    api_key: '', deployment: '', vector_store_id: '', assistant_id: '',
    prompt: '', temperature: 0.7, top_p: 1.0, max_tokens: 4096,
    search_index: '', allowed_groups: ['POCs'], connected_agents: [],
    connected_to: '', example_queries: ['', '', '', ''], _is_valid: true,
  });

  useEffect(() => {
    loadAssistants();
    loadVectorStores();
    loadSearchIndexes();
    loadDeployments();
    loadGroups();
  }, []);

  useEffect(() => {
    if ((editMode || createMode) && formRef.current) {
      setTimeout(() => formRef.current?.scrollTo(0, 0), 10);
    }
  }, [editMode, createMode, selectedKey]);

  const loadDeployments = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/deployments/list`);
      const data = await res.json();
      setDeployments(data.deployments || []);
    } catch {
      setDeployments([{ name: 'gpt-4', model: 'gpt-4' }, { name: 'gpt-4o', model: 'gpt-4o' }]);
    }
  };

  const loadGroups = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/groups/list`);
      const data = await res.json();
      setAvailableGroups(data.groups || []);
    } catch {
      setAvailableGroups(['POCs', 'Admins', 'Users']);
    }
  };

  const loadAssistants = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/assistants/config`);
      const data = await res.json();
      setAssistants(data.assistants || {});
    } catch {
      alert('Error loading assistants');
    } finally {
      setLoading(false);
    }
  };

  const loadVectorStores = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/vector-stores/list`);
      const data = await res.json();
      setVectorStores(data.vector_stores || []);
    } catch {}
  };

  const loadSearchIndexes = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/search-indexes/list`);
      const data = await res.json();
      setSearchIndexes(data.indexes || []);
    } catch {}
  };

  const handleEdit = (key) => {
    const a = assistants[key];
    setSelectedKey(key);
    setFormData({
      name: a.name || '', description: a.description || '', endpoint: a.endpoint || '',
      api_type: a.api_type || 'azure_ai_projects', api_key: a.api_key || '',
      deployment: a.deployment || '', vector_store_id: a.vector_store_id || '',
      assistant_id: a.assistant_id || '', prompt: a.prompt || '',
      temperature: a.temperature || 0.7, top_p: a.top_p || 1.0,
      max_tokens: a.max_tokens || 4096, search_index: a.search_index || '',
      allowed_groups: a.allowed_groups || ['POCs'], connected_agents: a.connected_agents || [],
      connected_to: a.connected_to || '',
      example_queries: a.example_queries || ['', '', '', ''],
      _is_valid: a._is_valid !== false,
    });
    setEditMode(true);
    setCreateMode(false);
    setSelectedFiles([]);
  };

  const handleCreate = () => {
    setSelectedKey(null);
    setFormData({
      name: '', description: '',
      endpoint: 'https://agentes-poc.services.ai.azure.com/api/projects/firstProject',
      api_type: 'azure_ai_projects', api_key: '', deployment: 'gpt-5',
      vector_store_id: '', assistant_id: '', prompt: '',
      temperature: 0.7, top_p: 1.0, max_tokens: 4096, search_index: '',
      allowed_groups: ['POCs'], connected_agents: [], connected_to: '',
      example_queries: ['What can you help me with?', 'Show me an example', 'How does this work?', 'Tell me more about your capabilities'],
      _is_valid: true,
    });
    setCreateMode(true);
    setEditMode(false);
    setSelectedFiles([]);
  };

  const handleDelete = async (key) => {
    if (!window.confirm(`Delete "${assistants[key]?.name}" assistant?`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/assistants/${key}`, { method: 'DELETE' });
      if (res.ok) {
        const updated = { ...assistants };
        const parent = updated[key]?.connected_to;
        if (parent && updated[parent]) {
          updated[parent] = { ...updated[parent], connected_agents: (updated[parent].connected_agents || []).filter(k => k !== key) };
        }
        delete updated[key];
        await fetch(`${API_BASE_URL}/api/assistants/config`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ assistants: updated }),
        });
        setAssistants(updated);
        setMessages([]);
        setCurrentConversationId(null);
        setWelcomeBox(true);
        setStats(null);
        alert('Assistant deleted');
      }
    } catch (err) {
      alert('Error deleting assistant: ' + err.message);
    }
  };

  const handleSave = async () => {
    if (!formData.name || !formData.endpoint || !formData.deployment) {
      alert('Please complete required fields: Name, Endpoint, Deployment');
      return;
    }
    const empty = formData.example_queries.filter(q => !q?.trim());
    if (empty.length > 0) {
      alert('Please complete all 4 example queries');
      return;
    }

    setSaving(true);
    try {
      let key = selectedKey;
      if (createMode) {
        key = formData.name.toLowerCase().replace(/\s+/g, '_');
        if (assistants[key]) { alert(`ID "${key}" already exists`); setSaving(false); return; }
      }

      const updated = {
        ...assistants,
        [key]: {
          name: formData.name, description: formData.description, endpoint: formData.endpoint,
          api_type: formData.api_type, api_key: formData.api_key, deployment: formData.deployment,
          vector_store_id: formData.vector_store_id, assistant_id: formData.assistant_id,
          prompt: formData.prompt, temperature: parseFloat(formData.temperature),
          top_p: parseFloat(formData.top_p), max_tokens: parseInt(formData.max_tokens),
          search_index: formData.search_index, allowed_groups: formData.allowed_groups,
          connected_agents: formData.connected_agents, connected_to: formData.connected_to,
          example_queries: formData.example_queries, _is_valid: true,
        },
      };

      // Sync connected_to
      if (formData.connected_agents?.length > 0) {
        formData.connected_agents.forEach(sub => {
          if (updated[sub]) updated[sub] = { ...updated[sub], connected_to: key };
        });
      }
      Object.keys(updated).forEach(k => {
        if (updated[k].connected_to === key && !formData.connected_agents?.includes(k)) {
          updated[k] = { ...updated[k], connected_to: '' };
        }
      });

      const res = await fetch(`${API_BASE_URL}/api/assistants/config`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assistants: updated }),
      });
      if (res.ok) {
        alert(createMode ? 'Assistant created' : 'Assistant updated');
        await loadAssistants();
        setEditMode(false);
        setCreateMode(false);
        setSelectedKey(null);
      } else {
        throw new Error('Save failed');
      }
    } catch (err) {
      alert('Error saving: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => { setEditMode(false); setCreateMode(false); setSelectedKey(null); setSelectedFiles([]); };

  const handleFormChange = (field, value) => setFormData(prev => ({ ...prev, [field]: value }));

  const handleDrag = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(e.type === 'dragenter' || e.type === 'dragover'); };
  const handleDrop = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); if (e.dataTransfer.files?.length > 0) setSelectedFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]); };
  const handleFileInput = (e) => { if (e.target.files?.length > 0) setSelectedFiles(prev => [...prev, ...Array.from(e.target.files)]); };
  const removeFile = (i) => setSelectedFiles(prev => prev.filter((_, idx) => idx !== i));

  const handleUploadFiles = async () => {
    if (!formData.vector_store_id) { alert('Select a Vector Store first'); return; }
    if (selectedFiles.length === 0) { alert('No files selected'); return; }
    setUploading(true);
    setUploadProgress(0);
    try {
      const fd = new FormData();
      fd.append('vector_store_id', formData.vector_store_id);
      selectedFiles.forEach(f => fd.append('files', f));
      const res = await fetch(`${API_BASE_URL}/api/vector-stores/upload`, { method: 'POST', body: fd });
      for (let i = 0; i <= 100; i += 10) { setUploadProgress(i); await new Promise(r => setTimeout(r, 200)); }
      if (res.ok) {
        const result = await res.json();
        alert(`${result.successful} files uploaded`);
        setSelectedFiles([]);
        setUploadProgress(0);
      } else throw new Error('Upload failed');
    } catch (err) {
      alert('Upload error: ' + err.message);
    } finally {
      setUploading(false);
    }
  };

  const filteredAssistants = Object.entries(assistants).filter(
    ([_, c]) => c.allowed_groups?.includes(groupUser) && !c.connected_to
  );

  return (
    <div className="am-overlay">
      <div className="am-panel">
        {loading ? (
          <div className="am-loading"><p>Loading assistants...</p></div>
        ) : editMode || createMode ? (
          /* ============ FORM ============ */
          <div className="am-form" ref={formRef}>
            <h3>{createMode ? 'Create Assistant' : `Edit: ${selectedKey}`}</h3>

            <section className="form-section">
              <h4>General</h4>
              <label>Name *<input type="text" value={formData.name} onChange={e => handleFormChange('name', e.target.value)} placeholder="Assistant name" required /></label>
              <label>Description<textarea value={formData.description} onChange={e => handleFormChange('description', e.target.value)} placeholder="Description" rows="2" /></label>
            </section>

            <section className="form-section">
              <h4>Azure OpenAI</h4>
              <label>API Type
                <select value={formData.api_type} onChange={e => handleFormChange('api_type', e.target.value)}>
                  <option value="azure_ai_projects">Azure AI Projects (Azure AD)</option>
                  <option value="azure">Azure OpenAI Service (API Key)</option>
                </select>
              </label>
              <label>Endpoint *<input type="url" value={formData.endpoint} onChange={e => handleFormChange('endpoint', e.target.value)} required /></label>
              {formData.api_type === 'azure' && (
                <label>API Key *<input type="password" value={formData.api_key} onChange={e => handleFormChange('api_key', e.target.value)} required /></label>
              )}
              <label>Deployment *
                <select value={formData.deployment} onChange={e => handleFormChange('deployment', e.target.value)} required>
                  <option value="">-- Select --</option>
                  {deployments.map(d => <option key={d.name} value={d.name}>{d.name} {d.model !== d.name ? `(${d.model})` : ''}</option>)}
                </select>
              </label>
              {formData.assistant_id && <label>Assistant ID<input type="text" value={formData.assistant_id} disabled /></label>}
            </section>

            <section className="form-section">
              <h4>Search</h4>
              <div className="tab-btns">
                <button type="button" className={searchTab === 'file_search' ? 'active' : ''} onClick={() => setSearchTab('file_search')}>File Search</button>
                <button type="button" className={searchTab === 'ai_search' ? 'active' : ''} onClick={() => setSearchTab('ai_search')}>AI Search</button>
              </div>

              {searchTab === 'file_search' && (
                <>
                  <label>Vector Store
                    <select value={formData.vector_store_id} onChange={e => handleFormChange('vector_store_id', e.target.value)}>
                      <option value="">-- Select --</option>
                      {vectorStores.map(vs => <option key={vs.id} value={vs.id}>{vs.name} ({vs.id})</option>)}
                    </select>
                  </label>
                  {formData.vector_store_id && (
                    <div className="drop-section">
                      <div className={`drop-zone ${dragActive ? 'active' : ''}`}
                        onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
                        onClick={() => document.getElementById('am-file-input').click()}>
                        <p>Drag files here or click to select</p>
                        <small>PDF, DOCX, TXT, MD, JSON, CSV, XLSX, PPTX, HTML</small>
                      </div>
                      <input id="am-file-input" type="file" multiple accept=".pdf,.docx,.doc,.txt,.md,.json,.csv,.xlsx,.pptx,.html" onChange={handleFileInput} style={{ display: 'none' }} />
                      {selectedFiles.length > 0 && (
                        <ul className="file-list">
                          {selectedFiles.map((f, i) => <li key={i}><span>{f.name}</span><button type="button" onClick={() => removeFile(i)}>✕</button></li>)}
                        </ul>
                      )}
                      {uploading && (
                        <div className="progress-bar"><div className="progress-fill" style={{ width: `${uploadProgress}%` }} /><span>{uploadProgress}%</span></div>
                      )}
                      <div className="upload-actions">
                        <button type="button" onClick={handleUploadFiles} disabled={uploading || selectedFiles.length === 0}>Upload</button>
                        <button type="button" onClick={() => setSelectedFiles([])} disabled={uploading || selectedFiles.length === 0}>Clear</button>
                      </div>
                    </div>
                  )}
                </>
              )}

              {searchTab === 'ai_search' && (
                <label>AI Search Index
                  <select value={formData.search_index} onChange={e => handleFormChange('search_index', e.target.value)}>
                    <option value="">-- Select --</option>
                    {searchIndexes.map(idx => <option key={idx.name} value={idx.name}>{idx.name} ({idx.document_count} docs)</option>)}
                  </select>
                </label>
              )}
            </section>

            <section className="form-section">
              <h4>Parameters</h4>
              <label>Temperature<input type="number" min="0" max="2" step="0.1" value={formData.temperature} onChange={e => handleFormChange('temperature', e.target.value)} /></label>
              <label>Top P<input type="number" min="0" max="1" step="0.1" value={formData.top_p} onChange={e => handleFormChange('top_p', e.target.value)} /></label>
              <label>Max Tokens<input type="number" min="100" max="128000" step="100" value={formData.max_tokens} onChange={e => handleFormChange('max_tokens', e.target.value)} /></label>
            </section>

            <section className="form-section">
              <h4>Access</h4>
              <div className="group-checks">
                {availableGroups.map(g => (
                  <label key={g} className="check-item">
                    <input type="checkbox" checked={formData.allowed_groups?.includes(g) || false}
                      onChange={e => {
                        const cur = formData.allowed_groups || [];
                        handleFormChange('allowed_groups', e.target.checked ? [...cur, g] : cur.filter(x => x !== g));
                      }} />
                    {g}
                  </label>
                ))}
              </div>
            </section>

            <section className="form-section">
              <h4>Sub-Agents</h4>
              {formData.connected_agents?.length > 0 ? (
                <div className="sub-grid">
                  {formData.connected_agents.map(subKey => {
                    const sub = assistants[subKey];
                    if (!sub) return null;
                    return (
                      <div key={subKey} className="sub-card">
                        <strong>{sub.name || subKey}</strong>
                        <p>{sub.description || 'No description'}</p>
                        <div className="sub-actions">
                          <button type="button" onClick={() => handleEdit(subKey)}>Edit</button>
                          <button type="button" className="danger" onClick={async () => {
                            await handleDelete(subKey);
                            handleFormChange('connected_agents', (formData.connected_agents || []).filter(a => a !== subKey));
                          }}>Delete</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : <p className="muted">No sub-agents configured</p>}
            </section>

            <section className="form-section">
              <h4>System Prompt</h4>
              <textarea value={formData.prompt} onChange={e => handleFormChange('prompt', e.target.value)} placeholder="Instructions..." rows="6" />
            </section>

            <section className="form-section">
              <h4>Example Queries</h4>
              {[0, 1, 2, 3].map(i => (
                <input key={i} type="text" value={formData.example_queries[i] || ''} placeholder={`Example ${i + 1}`}
                  onChange={e => { const q = [...formData.example_queries]; q[i] = e.target.value; handleFormChange('example_queries', q); }} required />
              ))}
            </section>
          </div>
        ) : (
          /* ============ LIST ============ */
          <div className="am-list">
            <div className="am-list-header">
              <h3>Assistants ({filteredAssistants.length})</h3>
              <button onClick={handleCreate}>+ Create</button>
            </div>
            {filteredAssistants.length === 0 ? (
              <div className="am-empty">
                <p>No assistants configured</p>
                <button onClick={handleCreate}>Create First Assistant</button>
              </div>
            ) : (
              <div className="am-grid">
                {filteredAssistants.map(([key, a]) => (
                  <div key={key} className="am-card">
                    <h4>{a.name || key}</h4>
                    <p className="muted">{a.description || 'No description'}</p>
                    <div className="am-card-meta">
                      <span>Model: {a.deployment}</span>
                      <span>Temp: {a.temperature}</span>
                    </div>
                    <div className="am-card-actions">
                      <button onClick={() => handleEdit(key)}>Edit</button>
                      <button className="danger" onClick={() => handleDelete(key)}>Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="am-footer">
          {editMode || createMode ? (
            <>
              <button className="primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              <button onClick={handleCancel} disabled={saving}>Cancel</button>
            </>
          ) : (
            <>
              <button onClick={onClose}>Close</button>
              <button onClick={loadAssistants}>Refresh</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default AssistantManager;
