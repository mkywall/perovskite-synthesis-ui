import { useState } from 'react';
import Login from './components/Login';
import MainForm from './components/MainForm';
import Summary from './components/Summary';
import './styles/App.css';

function App() {
  const [currentView, setCurrentView] = useState('login'); // 'login', 'main', 'summary'
  const [userInfo, setUserInfo] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [summaryMessage, setSummaryMessage] = useState('');
  const [summaryDetails, setSummaryDetails] = useState(null);

  const handleLoginSuccess = (user, token) => {
    setUserInfo(user);
    setSessionToken(token);
    setCurrentView('main');
  };

  const handleUploadSuccess = (message, summary) => {
    setSummaryMessage(message);
    setSummaryDetails(summary);
    setCurrentView('summary');
  };

  const handleAddMore = () => {
    setCurrentView('main');
    setSummaryMessage('');
    setSummaryDetails(null);
  };

  const handleLogout = () => {
    setUserInfo(null);
    setSessionToken(null);
    setSummaryMessage('');
    setSummaryDetails(null);
    localStorage.removeItem('sessionToken');
    setCurrentView('login');
  };

  return (
    <div className="app">
      <div className="container">
        {currentView === 'login' && (
          <Login onLoginSuccess={handleLoginSuccess} />
        )}

        {currentView === 'main' && userInfo && (
          <MainForm
            userInfo={userInfo}
            onUploadSuccess={handleUploadSuccess}
          />
        )}

        {currentView === 'summary' && (
          <Summary
            message={summaryMessage}
            summary={summaryDetails}
            onAddMore={handleAddMore}
            onLogout={handleLogout}
          />
        )}
      </div>
    </div>
  );
}

export default App;
