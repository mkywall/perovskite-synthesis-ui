import { useState, useEffect } from 'react';
import DataTable from './DataTable';
import { getSynthesisFields, uploadSynthesisData, resolveBatch } from '../services/api';

const MainForm = ({ userInfo, onUploadSuccess, onShowBatchResolution }) => {
  const [synthesisFields, setSynthesisFields] = useState({});
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedSynthesisType, setSelectedSynthesisType] = useState('');
  const [batchId, setBatchId] = useState('');
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Fetch synthesis fields on mount
  useEffect(() => {
    const fetchFields = async () => {
      try {
        const response = await getSynthesisFields();
        setSynthesisFields(response.fields);
      } catch (err) {
        console.error('Error fetching synthesis fields:', err);
        setError('Failed to load synthesis fields');
      }
    };

    fetchFields();
  }, []);

  const handleSynthesisTypeChange = (e) => {
    setSelectedSynthesisType(e.target.value);
    setTableData([]); // Clear table data when type changes
    setError('');
  };

  const handleUpload = async () => {
    setError('');

    // Validation
    if (!selectedProject) {
      setError('Please select a project');
      return;
    }

    if (!selectedSynthesisType) {
      setError('Please select a synthesis type');
      return;
    }

    if (!tableData || tableData.length === 0) {
      setError('Please enter at least one row of data');
      return;
    }

    setLoading(true);

    try {
      // If batch ID is provided, resolve it first
      if (batchId.trim()) {
        const resolution = await resolveBatch(
          batchId.trim(),
          userInfo.orcid,
          selectedProject
        );

        if (resolution.status === 'not_found' || resolution.status === 'multiple_matches') {
          // Show batch resolution UI
          onShowBatchResolution(resolution, {
            project: selectedProject,
            synthesisType: selectedSynthesisType,
            data: tableData
          });
          setLoading(false);
          return;
        }

        // If resolved, proceed with upload using resolved batch_id
        await performUpload(resolution.batch_id);
      } else {
        // No batch ID, proceed with upload
        await performUpload(null);
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || 'An error occurred during upload');
      setLoading(false);
    }
  };

  const performUpload = async (resolvedBatchId) => {
    try {
      const uploadData = {
        email: userInfo.email,
        orcid: userInfo.orcid,
        user_name: userInfo.name,
        project: selectedProject,
        synthesis_type: selectedSynthesisType,
        batch_id: resolvedBatchId,
        data: tableData
      };

      const response = await uploadSynthesisData(uploadData);

      if (response.success) {
        onUploadSuccess(response.message, response.summary);
      } else {
        setError(response.message || 'Upload failed');
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || 'An error occurred during upload');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setSelectedSynthesisType('');
    setTableData([]);
    setBatchId('');
    setError('');
  };

  const currentFields = selectedSynthesisType ? synthesisFields[selectedSynthesisType] || [] : [];
  const showTable = selectedSynthesisType && currentFields.length > 0;

  return (
    <div className="main-form">
      <div className="user-info-box">
        <strong>Current User:</strong> {userInfo.name} | <strong>Email:</strong> {userInfo.email} | <strong>ORCID:</strong> {userInfo.orcid}
      </div>

      <div className="form-section">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="project">Project *</label>
            <select
              id="project"
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              disabled={loading}
            >
              <option value="">-- Select a project --</option>
              {userInfo.projects.map((project) => (
                <option key={project} value={project}>
                  {project}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="synthesisType">Synthesis Type *</label>
            <select
              id="synthesisType"
              value={selectedSynthesisType}
              onChange={handleSynthesisTypeChange}
              disabled={loading}
            >
              <option value="">-- Select synthesis type --</option>
              {Object.keys(synthesisFields).map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="batchId">Batch ID (Optional)</label>
            <input
              id="batchId"
              type="text"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              placeholder="Enter batch ID to link samples"
              disabled={loading}
            />
          </div>
        </div>

        {showTable && (
          <>
            <div className="table-section">
              <h3>Enter Sample Data</h3>
              <DataTable
                fields={currentFields}
                onChange={setTableData}
                operatorName={userInfo.name}
              />
            </div>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            <div className="button-group">
              <button
                className="btn btn-primary btn-large"
                onClick={handleUpload}
                disabled={loading}
              >
                {loading ? 'Uploading...' : 'Upload Data'}
              </button>
              <button
                className="btn btn-secondary btn-large"
                onClick={handleCancel}
                disabled={loading}
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default MainForm;
