import { createContext, useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {

  // Auth & session (login disabled)
  // const [authenticated, setAuthenticated] = useState(false);
  // const [sessionTimestamp, setSessionTimestamp] = useState(null);

  // User
  // const [loggedUser, setLoggedUser] = useState(() => {
  //   return sessionStorage.getItem('userId') || `temp_${Date.now()}`;
  // });

  // const [groupUser, setGroupUser] = useState(() => {
  //   return sessionStorage.getItem('groupUser') || null;
  // });
  const [loggedUser, setLoggedUser] = useState('default_user');
  const [groupUser, setGroupUser] = useState('POCs');

  // Assistants
  const [assistants, setAssistants] = useState({});
  const [selectedAssistant, setSelectedAssistant] = useState(null);
  const [assistantsConfig, setAssistantsConfig] = useState({});
  const [showAssistantManager, setShowAssistantManager] = useState(false);

  // Conversations
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState(null);
  const [updateStats, setUpdateStats] = useState(false);

  // Mode
  const [ragMode, setRagMode] = useState('assistant');
  const [welcomeBox, setWelcomeBox] = useState(true);

  // Loading
  const [loadingAssistants, setLoadingAssistants] = useState(true);
  const [isFiltering, setIsFiltering] = useState(false);
  const [enableWrite, setEnableWrite] = useState(true);

  // GPT Mode
  const [gptMode, setGptMode] = useState(false);

  useEffect(() => {
    const loadGptMode = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/gptmode`);
        const data = await response.json();
        setGptMode(data.gpt_mode_active || false);
      } catch {
        setGptMode(false);
      }
    };
    loadGptMode();
  }, []);

  return (
    <AuthContext.Provider value={{
      // authenticated, setAuthenticated,
      // sessionTimestamp, setSessionTimestamp,
      loggedUser, setLoggedUser,
      groupUser, setGroupUser,
      assistants, setAssistants,
      selectedAssistant, setSelectedAssistant,
      assistantsConfig, setAssistantsConfig,
      showAssistantManager, setShowAssistantManager,
      conversations, setConversations,
      currentConversationId, setCurrentConversationId,
      messages, setMessages,
      stats, setStats,
      updateStats, setUpdateStats,
      ragMode, setRagMode,
      welcomeBox, setWelcomeBox,
      loadingAssistants, setLoadingAssistants,
      isFiltering, setIsFiltering,
      enableWrite, setEnableWrite,
      gptMode, setGptMode,
    }}>
      {children}
    </AuthContext.Provider>
  );
};
