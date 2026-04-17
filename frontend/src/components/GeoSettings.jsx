import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * GeoSettings Component
 *
 * Manages GEO (Generative Engine Optimization) configuration for image metadata generation.
 * Allows users to configure organization identity, geographic matrix, and AI preferences
 * on a per-domain basis.
 */
export default function GeoSettings({ domain, isOpen, onClose }) {
  const [config, setConfig] = useState({
    org_name: '',
    topic_entities: [],
    primary_location: '',
    location_pool: [],
    model: 'gemini-1.5-pro',
    temperature: 0.4,
    max_tokens: 500,
    client_name: '',
    prepared_by: '',
  });

  const [newTopicEntity, setNewTopicEntity] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);

  // Load config on mount
  useEffect(() => {
    if (isOpen && domain) {
      loadConfig();
    }
  }, [isOpen, domain]);

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/geo/settings?domain=${encodeURIComponent(domain)}`);
      if (!response.ok) throw new Error('Failed to load GEO configuration');
      const data = await response.json();
      setConfig({
        org_name: data.org_name || '',
        topic_entities: data.topic_entities || [],
        primary_location: data.primary_location || '',
        location_pool: data.location_pool || [],
        model: data.model || 'gemini-1.5-pro',
        temperature: data.temperature || 0.4,
        max_tokens: data.max_tokens || 500,
        client_name: data.client_name || '',
        prepared_by: data.prepared_by || '',
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    setValidationErrors([]);

    try {
      const response = await fetch(`${API_BASE}/api/geo/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain,
          ...config,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.detail && data.detail.errors) {
          setValidationErrors(data.detail.errors);
        }
        throw new Error(data.detail?.message || 'Failed to save configuration');
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const addTopicEntity = () => {
    if (!newTopicEntity.trim()) return;

    // Split by comma, trim each, filter out empties and duplicates
    const entities = newTopicEntity
      .split(',')
      .map(e => e.trim())
      .filter(e => e && !config.topic_entities.includes(e));

    if (entities.length > 0) {
      setConfig({
        ...config,
        topic_entities: [...config.topic_entities, ...entities],
      });
      setNewTopicEntity('');
    }
  };

  const removeTopicEntity = (entity) => {
    setConfig({
      ...config,
      topic_entities: config.topic_entities.filter(e => e !== entity),
    });
  };

  const addLocation = () => {
    if (!newLocation.trim()) return;

    // Split by comma, trim each, filter out empties and duplicates
    const locations = newLocation
      .split(',')
      .map(l => l.trim())
      .filter(l => l && !config.location_pool.includes(l));

    if (locations.length > 0) {
      setConfig({
        ...config,
        location_pool: [...config.location_pool, ...locations],
      });
      setNewLocation('');
    }
  };

  const removeLocation = (location) => {
    setConfig({
      ...config,
      location_pool: config.location_pool.filter(l => l !== location),
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">GEO Settings</h2>
            <p className="text-sm text-gray-600 mt-1">Configure image metadata optimization for <span className="font-mono text-blue-600">{domain}</span></p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors text-2xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {loading && (
            <div className="text-center py-8 text-gray-600">
              Loading configuration...
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <span className="text-red-600 flex-shrink-0 text-xl">⚠️</span>
              <div className="text-red-800 text-sm">{error}</div>
            </div>
          )}

          {success && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
              <span className="text-green-600 flex-shrink-0 text-xl">✓</span>
              <div className="text-green-800 text-sm">Configuration saved successfully!</div>
            </div>
          )}

          {validationErrors.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="font-semibold text-yellow-800 mb-2">Validation Errors:</div>
              <ul className="list-disc list-inside text-yellow-700 text-sm space-y-1">
                {validationErrors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}

          {!loading && (
            <>
              {/* Organization Identity */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">Organization Identity</h3>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Organization Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.org_name}
                    onChange={(e) => setConfig({ ...config, org_name: e.target.value })}
                    placeholder="e.g., Living Systems Counselling"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">The official name of your organization</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Topic Entities <span className="text-red-500">*</span>
                  </label>
                  <div className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={newTopicEntity}
                      onChange={(e) => setNewTopicEntity(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTopicEntity())}
                      placeholder="e.g., Bowen Theory, Systems Thinking (comma-separated)"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      onClick={addTopicEntity}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1"
                    >
                      <span className="text-lg leading-none">+</span>
                      Add
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {config.topic_entities.map((entity, idx) => (
                      <div key={idx} className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full flex items-center gap-2 text-sm">
                        <span>{entity}</span>
                        <button
                          onClick={() => removeTopicEntity(entity)}
                          className="text-blue-600 hover:text-blue-800 font-bold leading-none"
                          aria-label="Remove"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">Topics, theories, or services (add multiple with commas)</p>
                </div>
              </div>

              {/* Geographic Matrix */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">Geographic Matrix</h3>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Primary Location <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.primary_location}
                    onChange={(e) => setConfig({ ...config, primary_location: e.target.value })}
                    placeholder="e.g., Vancouver"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">Your main service location</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Location Pool <span className="text-red-500">*</span>
                  </label>
                  <div className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={newLocation}
                      onChange={(e) => setNewLocation(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addLocation())}
                      placeholder="e.g., North Vancouver, Burnaby, Lower Mainland (comma-separated)"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      onClick={addLocation}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1"
                    >
                      <span className="text-lg leading-none">+</span>
                      Add
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {config.location_pool.map((location, idx) => (
                      <div key={idx} className="bg-green-100 text-green-800 px-3 py-1 rounded-full flex items-center gap-2 text-sm">
                        <span>{location}</span>
                        <button
                          onClick={() => removeLocation(location)}
                          className="text-green-600 hover:text-green-800 font-bold leading-none"
                          aria-label="Remove"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">Secondary locations for broader SEO reach (add multiple with commas)</p>
                </div>
              </div>

              {/* API Preferences */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">AI Model Preferences</h3>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    value={config.model}
                    onChange={(e) => setConfig({ ...config, model: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="gemini-1.5-pro">Gemini 1.5 Pro (Recommended)</option>
                    <option value="gemini-1.5-flash">Gemini 1.5 Flash (Faster)</option>
                    <option value="gpt-4o">GPT-4o (OpenAI)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Temperature: {config.temperature}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={config.temperature}
                    onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                  <p className="text-xs text-gray-500 mt-1">Lower = more focused, Higher = more creative (0.4 recommended)</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Tokens
                  </label>
                  <input
                    type="number"
                    min="100"
                    max="4000"
                    step="50"
                    value={config.max_tokens}
                    onChange={(e) => setConfig({ ...config, max_tokens: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">Maximum length of AI response (500 recommended)</p>
                </div>
              </div>

              {/* Report Preferences */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">Report Customization</h3>
                <p className="text-sm text-gray-600">Customize how your PDF audit reports are labeled</p>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Client/Company Name
                  </label>
                  <input
                    type="text"
                    value={config.client_name}
                    onChange={(e) => setConfig({ ...config, client_name: e.target.value })}
                    placeholder="e.g., Living Systems Counselling"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">Appears as "Prepared for:" on PDF cover page (defaults to domain if empty)</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Prepared By
                  </label>
                  <input
                    type="text"
                    value={config.prepared_by}
                    onChange={(e) => setConfig({ ...config, prepared_by: e.target.value })}
                    placeholder="e.g., Your Agency Name or Your Name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">Appears as "Prepared by:" on PDF cover page (optional)</p>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 hover:text-gray-900 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Saving...
              </>
            ) : (
              <>
                💾 Save Configuration
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
