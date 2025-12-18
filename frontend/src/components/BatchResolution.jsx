import { useState } from 'react';
import { createBatch } from '../services/api';

const BatchResolution = ({ resolution, userInfo, project, onResolve, onCancel }) => {
  const [selectedBatch, setSelectedBatch] = useState('');
  const [batchName, setBatchName] = useState('');
  const [batchId, setBatchId] = useState(resolution.input || '');
  const [batchDescription, setBatchDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Handle creating a new batch
  const handleCreateBatch = async () => {
    setError('');

    if (!batchName.trim()) {
      setError('Batch name is required');
      return;
    }

    if (!batchId.trim()) {
      setError('Batch ID is required');
      return;
    }

    setLoading(true);

    try {
      const response = await createBatch({
        batch_name: batchName,
        batch_id: batchId,
        batch_description: batchDescription,
        orcid: userInfo.orcid,
        project: project
      });

      if (response.success) {
        // Resolve with the new batch unique_id
        onResolve(response.unique_id);
      } else {
        setError(response.message || 'Failed to create batch');
      }
    } catch (err) {
      console.error('Batch creation error:', err);
      setError(err.response?.data?.detail || 'An error occurred while creating the batch');
    } finally {
      setLoading(false);
    }
  };

  // Handle selecting from multiple matches
  const handleSelectBatch = () => {
    if (!selectedBatch) {
      setError('Please select a batch from the list');
      return;
    }

    // Extract unique_id from the selected value
    const match = resolution.matches.find(m => m.unique_id === selectedBatch);
    if (match) {
      onResolve(match.unique_id);
    }
  };

  // Render different UI based on resolution status
  if (resolution.status === 'not_found') {
    return (
      <div className="batch-resolution">
        <h2>Batch ID Resolution</h2>
        <div className="warning-message">
          Batch ID '{resolution.input}' not found. Please create a new batch or cancel to skip batch linking.
        </div>

        <div className="batch-form">
          <h3>Create New Batch</h3>

          <div className="form-group">
            <label htmlFor="batchName">Batch Name *</label>
            <input
              id="batchName"
              type="text"
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              placeholder="Enter a descriptive name for the batch"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="batchId">Batch ID *</label>
            <input
              id="batchId"
              type="text"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              placeholder="Enter unique batch identifier"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="batchDescription">Batch Description</label>
            <input
              id="batchDescription"
              type="text"
              value={batchDescription}
              onChange={(e) => setBatchDescription(e.target.value)}
              placeholder="Enter batch description (optional)"
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="button-group">
            <button
              className="btn btn-primary"
              onClick={handleCreateBatch}
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Batch'}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => onCancel()}
              disabled={loading}
            >
              Cancel (Skip Batch Linking)
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (resolution.status === 'multiple_matches') {
    return (
      <div className="batch-resolution">
        <h2>Batch ID Resolution</h2>
        <div className="warning-message">
          Multiple batches found with name '{resolution.input}'. Please select one:
        </div>

        <div className="batch-selection">
          <div className="form-group">
            <label htmlFor="batchSelect">Select Batch</label>
            <select
              id="batchSelect"
              value={selectedBatch}
              onChange={(e) => setSelectedBatch(e.target.value)}
            >
              <option value="">-- Select a batch --</option>
              {resolution.matches.map((match) => (
                <option key={match.unique_id} value={match.unique_id}>
                  {match.sample_name} ({match.unique_id})
                  {match.description && ` - ${match.description}`}
                </option>
              ))}
            </select>
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="button-group">
            <button
              className="btn btn-primary"
              onClick={handleSelectBatch}
            >
              Confirm Selection
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => onCancel()}
            >
              Cancel (Skip Batch Linking)
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default BatchResolution;
