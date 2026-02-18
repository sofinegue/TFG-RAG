import { useState, useEffect, useContext, useRef } from 'react';
import Message from './Message';
import { AuthContext } from './Context';
import { API_BASE_URL } from '../config';
import './ChatInterface.css';

const ChatInterface = () => {
  const {
    selectedAssistant,
    assistants,
    setUpdateStats,
    messages, setMessages,
    conversations, setConversations,
    currentConversationId, setCurrentConversationId,
    loggedUser,
    welcomeBox, setWelcomeBox,
    loadingAssistants,
    enableWrite, setEnableWrite,
  } = useContext(AuthContext);

  const assistantInfo = selectedAssistant ? assistants[selectedAssistant] : null;

  const [userInput, setUserInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingDots, setLoadingDots] = useState('');
  const messagesEndRef = useRef(null);

  const [exampleQueries, setExampleQueries] = useState([
    'Who is the most experienced person in Python and Azure?',
    'Find candidates with cloud computing certifications',
    'Who is Senior or Manager with advanced English?',
  ]);

  // Update example queries when assistant changes
  useEffect(() => {
    if (assistantInfo?.example_queries && Array.isArray(assistantInfo.example_queries)) {
      const queries = assistantInfo.example_queries.filter(q => q && q.trim() !== '');
      if (queries.length > 0) {
        setExampleQueries(queries);
        return;
      }
    }
    setExampleQueries([
      'Who is the most experienced person in Python and Azure?',
      'Find candidates with cloud computing certifications',
      'Who is Senior or Manager with advanced English?',
    ]);
  }, [selectedAssistant, assistantInfo]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Loading dots animation
  useEffect(() => {
    if (!isLoading) { setLoadingDots(''); return; }
    let count = 0;
    const interval = setInterval(() => {
      count = (count + 1) % 4;
      setLoadingDots('.'.repeat(count));
    }, 400);
    return () => clearInterval(interval);
  }, [isLoading]);

  // Group consecutive messages from the same role
  const groupMessages = (msgs) => {
    return msgs.reduce((acc, msg) => {
      const prev = acc[acc.length - 1];
      if (prev && prev.role === msg.role) {
        prev.content += '\n\n' + msg.content;
        if (msg.metadata) prev.metadata = { ...(prev.metadata || {}), ...msg.metadata };
        if (msg.sources) prev.sources = [...(prev.sources || []), ...msg.sources];
      } else {
        acc.push({ ...msg });
      }
      return acc;
    }, []);
  };

  const handleSend = async (customQuery) => {
    const query = customQuery || userInput;
    if (!query.trim()) return;
    if (!selectedAssistant) return;

    setIsLoading(true);
    setEnableWrite(false);
    setWelcomeBox(false);
    setUserInput('');
    setMessages(prev => [...prev, { role: 'user', content: query }]);

    try {
      const formData = new FormData();
      formData.append('query', query);
      formData.append('user_id', loggedUser || 'anonymous');
      formData.append('rag_mode', 'assistant');
      formData.append('show_timestamps', 'false');
      formData.append('assistant_id', selectedAssistant);
      if (currentConversationId) {
        formData.append('conversation_id', currentConversationId);
      }

      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (data.conversation_id && data.messages && setConversations) {
        setConversations(prevConvs => {
          const arr = Array.isArray(prevConvs) ? prevConvs : [];
          const exists = arr.find(c => c.id === data.conversation_id);
          if (exists) {
            return arr.map(c =>
              c.id === data.conversation_id ? { ...c, messages: data.messages } : c
            );
          }
          return [...arr, {
            id: data.conversation_id,
            title: data.messages[0]?.content || 'New conversation',
            messages: data.messages,
            created_at: data.created_at,
          }];
        });
        setCurrentConversationId(data.conversation_id);
      }

      if (!res.ok) throw new Error(data.error || 'Unknown error');

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        metadata: data.metadata,
        timestamps: data.timestamps,
      }]);
    } catch (err) {
      console.error('Error sending message:', err);
    } finally {
      setUpdateStats(true);
      setEnableWrite(true);
      setIsLoading(false);
    }
  };

  const grouped = groupMessages(messages);

  return (
    <div className="chat-wrapper">
      <div className="chat-messages">
        {welcomeBox && !isLoading && (
          <div className="welcome-box">
            <h2>Welcome</h2>
            <p>Ask a question or choose one of the examples below:</p>
            <div className="example-queries">
              {exampleQueries.map((q, i) => (
                <button key={i} className="example-btn" onClick={() => handleSend(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {grouped.map((msg, idx) => (
          <Message key={idx} message={msg} showSources={conversations} selectedAssistant={assistantInfo} />
        ))}

        {isLoading && (
          <div className="msg-row assistant">
            <div className="msg-bubble assistant loading-bubble">
              <span className="msg-author">Assistant</span>
              <span>Thinking{loadingDots}</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-bar">
        <input
          type="text"
          value={userInput}
          onChange={e => setUserInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSend(); } }}
          placeholder="Type your message..."
          disabled={!enableWrite || loadingAssistants}
        />
        <button
          onClick={() => handleSend()}
          disabled={!enableWrite || loadingAssistants || !userInput.trim()}
          className="send-btn"
        >
          ↑
        </button>
      </div>
    </div>
  );
};

export default ChatInterface;
