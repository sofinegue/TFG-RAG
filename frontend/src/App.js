import { useState, useEffect, useContext } from 'react';
import { AuthProvider, AuthContext } from './components/Context';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
// import LoginScreen from './components/LoginScreen';
import './App.css';
import { API_BASE_URL } from './config';

function AppContent() {
  const {
    // authenticated, setAuthenticated,
    // setLoggedUser,
    setAssistantsConfig,
    showAssistantManager,
  } = useContext(AuthContext);

  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768);

  // Load assistants config on mount
  useEffect(() => {
    // const auth = sessionStorage.getItem('authenticated') === 'true';
    // const timestamp = parseInt(sessionStorage.getItem('session_timestamp'), 10);
    // const storedUserId = sessionStorage.getItem('userId');
    // const now = Date.now();

    // if (auth && timestamp && now - timestamp > 30 * 60 * 1000) {
    //   sessionStorage.removeItem('authenticated');
    //   sessionStorage.removeItem('session_timestamp');
    //   sessionStorage.removeItem('userId');
    //   setAuthenticated(false);
    //   setLoggedUser('');
    // } else {
    //   setAuthenticated(auth);
    //   if (auth && storedUserId) {
    //     setLoggedUser(storedUserId);
    //   }
    // }

    const loadAssistantsConfig = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/assistants/config`);
        const data = await response.json();
        setAssistantsConfig(data.assistants || {});
      } catch (error) {
        console.error('Error loading assistants config:', error);
      }
    };
    loadAssistantsConfig();
  }, []);

  // Responsive sidebar
  useEffect(() => {
    const handleResize = () => setSidebarOpen(window.innerWidth >= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleSidebar = () => setSidebarOpen(prev => !prev);

  // const handleLoginSuccess = (user) => {
  //   setAuthenticated(true);
  //   sessionStorage.setItem('authenticated', 'true');
  //   sessionStorage.setItem('session_timestamp', Date.now().toString());
  //   setLoggedUser(user);
  //   sessionStorage.setItem('userId', user);
  // };

  return (
    <div className="app-container">
      {/* Login disabled — always show main UI */}
      {/* {authenticated ? ( */}
      <Header />
      <div className="app-layout">
        {!showAssistantManager && (
          <button
            className={`sidebar-toggle ${sidebarOpen ? 'open' : ''}`}
            onClick={toggleSidebar}
            aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            {sidebarOpen ? '✕' : '☰'}
          </button>
        )}

        <aside className={`sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
          <Sidebar />
        </aside>

        {sidebarOpen && window.innerWidth < 768 && (
          <div className="sidebar-overlay" onClick={toggleSidebar} />
        )}

        <main className="main-content">
          <ChatInterface />
        </main>
      </div>
    </div>
    // ) : (
    //   <LoginScreen onLoginSuccess={handleLoginSuccess} />
    // )}
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
