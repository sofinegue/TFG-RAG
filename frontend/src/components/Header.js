// import { useContext } from 'react';
// import { AuthContext } from './Context';
import './Header.css';

const Header = () => {
  // const {
  //   setSelectedAssistant, setStats, setAuthenticated,
  //   setMessages, setConversations, setCurrentConversationId,
  //   setLoggedUser, setWelcomeBox,
  // } = useContext(AuthContext);

  // const handleLogout = () => {
  //   setAuthenticated(false);
  //   setLoggedUser('');
  //   setMessages([]);
  //   setCurrentConversationId(null);
  //   setConversations([]);
  //   setWelcomeBox(true);
  //   setSelectedAssistant(null);
  //   setStats(null);
  //   sessionStorage.removeItem('authenticated');
  //   sessionStorage.removeItem('session_timestamp');
  //   sessionStorage.removeItem('userId');
  // };

  return (
    <header className="header-bar">
      <h1 className="header-title">RAG Chat</h1>
      {/* <button className="logout-btn" onClick={handleLogout} aria-label="Logout" title="Log out">⏻</button> */}
    </header>
  );
};

export default Header;
