import { useState } from 'react';
import Login from './components/Login';
import MainForm from './components/MainForm';
import BatchResolution from './components/BatchResolution';
import Summary from './components/Summary';
import { uploadSynthesisData } from './services/api';
import './styles/App.css';

function App() {
  // Application state
  const [currentView, setCurrentView] = useState('login'); // 'login', 'main', 'batch_resolution', 'summary'
  const [userInfo, setUserInfo] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);

  // Batch resolution state
  const [batchResolution, setBatchResolution] = useState(null);
  const [pendingUploadData, setPendingUploadData] = useState(null);

  // Summary state
  const [summaryMessage, setSummaryMessage] = useState('');
  const [summaryDetails, setSummaryDetails] = useState(null);

  // Handle successful login
  const handleLoginSuccess = (user, token) => {
    setUserInfo(user);
    setSessionToken(token);
    setCurrentView('main');
  };

  // Handle showing batch resolution
  const handleShowBatchResolution = (resolution, uploadData) => {
    setBatchResolution(resolution);
    setPendingUploadData(uploadData);
    setCurrentView('batch_resolution');
  };

  // Handle batch resolution complete
  const handleBatchResolved = async (resolvedBatchId) => {
    // Proceed with upload using resolved batch ID
    try {
      const uploadData = {
        email: userInfo.email,
        orcid: userInfo.orcid,
        user_name: userInfo.name,
        project: pendingUploadData.project,
        synthesis_type: pendingUploadData.synthesisType,
        batch_id: resolvedBatchId,
        data: pendingUploadData.data
      };

      const response = await uploadSynthesisData(uploadData);

      if (response.success) {
        setSummaryMessage(response.message);
        setSummaryDetails(response.summary);
        setCurrentView('summary');
      } else {
        alert('Upload failed: ' + response.message);
        setCurrentView('main');
      }
    } catch (err) {
      console.error('Upload error:', err);
      alert('Upload error: ' + (err.response?.data?.detail || err.message));
      setCurrentView('main');
    }

    // Clear batch resolution state
    setBatchResolution(null);
    setPendingUploadData(null);
  };

  // Handle batch resolution cancelled
  const handleBatchResolutionCancel = async () => {
    // Proceed with upload without batch ID
    try {
      const uploadData = {
        email: userInfo.email,
        orcid: userInfo.orcid,
        user_name: userInfo.name,
        project: pendingUploadData.project,
        synthesis_type: pendingUploadData.synthesisType,
        batch_id: null,
        data: pendingUploadData.data
      };

      const response = await uploadSynthesisData(uploadData);

      if (response.success) {
        setSummaryMessage(response.message);
        setSummaryDetails(response.summary);
        setCurrentView('summary');
      } else {
        alert('Upload failed: ' + response.message);
        setCurrentView('main');
      }
    } catch (err) {
      console.error('Upload error:', err);
      alert('Upload error: ' + (err.response?.data?.detail || err.message));
      setCurrentView('main');
    }

    // Clear batch resolution state
    setBatchResolution(null);
    setPendingUploadData(null);
  };

  // Handle upload success (when no batch resolution needed)
  const handleUploadSuccess = (message, summary) => {
    setSummaryMessage(message);
    setSummaryDetails(summary);
    setCurrentView('summary');
  };

  // Handle add more data
  const handleAddMore = () => {
    setCurrentView('main');
    setSummaryMessage('');
    setSummaryDetails(null);
  };

  // Handle logout
  const handleLogout = () => {
    setUserInfo(null);
    setSessionToken(null);
    setSummaryMessage('');
    setSummaryDetails(null);
    setBatchResolution(null);
    setPendingUploadData(null);
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
            onShowBatchResolution={handleShowBatchResolution}
          />
        )}

        {currentView === 'batch_resolution' && batchResolution && (
          <BatchResolution
            resolution={batchResolution}
            userInfo={userInfo}
            project={pendingUploadData?.project}
            onResolve={handleBatchResolved}
            onCancel={handleBatchResolutionCancel}
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
