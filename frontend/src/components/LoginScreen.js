import { useState, useContext } from 'react';
import { AuthContext } from './Context';
import { API_BASE_URL } from '../config';
import './LoginScreen.css';

const LoginScreen = ({ onLoginSuccess }) => {
  const {
    setAuthenticated,
    setLoggedUser,
    setGroupUser,
    setSessionTimestamp,
    setShowAssistantManager,
  } = useContext(AuthContext);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleLogin = async () => {
    if (!username || !password) {
      setErrorMsg('Please fill in all fields');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const res = await fetch(`${API_BASE_URL}/api/login`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (data.authenticated) {
        setAuthenticated(true);
        setLoggedUser(data.user);
        setGroupUser(data.group);
        sessionStorage.setItem('groupUser', data.group);
        setSessionTimestamp(Date.now());
        setShowAssistantManager(false);
        onLoginSuccess(data.user);
      } else {
        setErrorMsg(data.error || 'Incorrect username or password');
      }
    } catch (error) {
      setErrorMsg('Connection error: ' + error.message);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleLogin();
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-header">
          <h1>RAG Chat</h1>
          <p>Sign in to continue</p>
        </div>

        <div className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={handleKeyDown}
              autoComplete="username"
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              autoComplete="current-password"
            />
          </div>
          <button className="login-btn" onClick={handleLogin}>
            Log In
          </button>
          {errorMsg && <p className="error-msg">{errorMsg}</p>}
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
