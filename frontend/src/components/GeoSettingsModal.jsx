import { useState, useEffect } from 'react'
import { getGeoSettings, saveGeoSettings, getGeoAiModel, setGeoAiModel } from '../api.js'

/**
 * Modal for configuring GEO (Generative Engine Optimization) settings.
 *
 * Allows users to set organization identity and geographic context for
 * AI-powered image metadata generation.
 */
export default function GeoSettingsModal({ domain, onClose, onSaved }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Form fields
  const [orgName, setOrgName] = useState('')
  const [primaryLocation, setPrimaryLocation] = useState('')
  const [topicEntities, setTopicEntities] = useState([''])
  const [locationPool, setLocationPool] = useState([''])

  // AI model selection
  const [availableModels, setAvailableModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')

  // Load existing configuration and models
  useEffect(() => {
    async function load() {
      try {
        const [config, modelData] = await Promise.all([
          getGeoSettings(domain),
          getGeoAiModel().catch(() => ({ available: [], selected: null })),
        ])
        setOrgName(config.org_name || '')
        setPrimaryLocation(config.primary_location || '')
        setTopicEntities(config.topic_entities?.length ? config.topic_entities : [''])
        setLocationPool(config.location_pool?.length ? config.location_pool : [''])
        setAvailableModels(modelData.available || [])
        setSelectedModel(modelData.selected || '')
      } catch (err) {
        console.error('Failed to load GEO settings:', err)
        setError('Failed to load settings: ' + err.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [domain])

  const handleModelChange = async (modelId) => {
    setSelectedModel(modelId)
    await setGeoAiModel(modelId).catch(err => console.error('Failed to save model:', err))
  }

  const handleSave = async () => {
    // Validate required fields
    if (!orgName.trim()) {
      alert('Organization name is required')
      return
    }
    if (!primaryLocation.trim()) {
      alert('Primary location is required')
      return
    }

    const validTopics = topicEntities.filter(t => t.trim())
    const validLocations = locationPool.filter(l => l.trim())

    if (validTopics.length === 0) {
      alert('At least one topic entity is required')
      return
    }
    if (validLocations.length === 0) {
      alert('At least one location in the pool is required')
      return
    }

    setSaving(true)
    setError(null)

    try {
      await saveGeoSettings({
        domain,
        org_name: orgName.trim(),
        primary_location: primaryLocation.trim(),
        topic_entities: validTopics,
        location_pool: validLocations,
        model: 'gemini-1.5-pro',
        temperature: 0.4,
        max_tokens: 500,
        client_name: '',
        prepared_by: '',
      })

      if (onSaved) onSaved()
      onClose()
    } catch (err) {
      console.error('Failed to save GEO settings:', err)
      setError('Failed to save settings: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const addTopicEntity = () => {
    setTopicEntities([...topicEntities, ''])
  }

  const removeTopicEntity = (index) => {
    setTopicEntities(topicEntities.filter((_, i) => i !== index))
  }

  const updateTopicEntity = (index, value) => {
    const updated = [...topicEntities]
    updated[index] = value
    setTopicEntities(updated)
  }

  const addLocation = () => {
    setLocationPool([...locationPool, ''])
  }

  const removeLocation = (index) => {
    setLocationPool(locationPool.filter((_, i) => i !== index))
  }

  const updateLocation = (index, value) => {
    const updated = [...locationPool]
    updated[index] = value
    setLocationPool(updated)
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl shadow-2xl p-8 max-w-2xl w-full mx-4">
          <p className="text-center text-gray-600">Loading GEO settings...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full my-8">
        {/* Header */}
        <div className="border-b border-gray-200 p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-black text-gray-800">GEO Configuration</h2>
              <p className="text-sm text-gray-600 mt-1">Configure settings for {domain}</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Organization Name */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Organization Name *
            </label>
            <input
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="e.g., Living Systems Counselling"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">
              Your organization's name as it should appear in metadata
            </p>
          </div>

          {/* Primary Location */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Primary Location *
            </label>
            <input
              type="text"
              value={primaryLocation}
              onChange={(e) => setPrimaryLocation(e.target.value)}
              placeholder="e.g., Vancouver"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">
              Main city or region for your organization
            </p>
          </div>

          {/* Topic Entities */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Topic Entities * <span className="text-xs font-normal text-gray-500">(at least 1 required)</span>
            </label>
            <div className="space-y-2">
              {topicEntities.map((entity, index) => (
                <div key={`topic-${index}-${entity}`} className="flex gap-2">
                  <input
                    type="text"
                    value={entity}
                    onChange={(e) => updateTopicEntity(index, e.target.value)}
                    placeholder="e.g., Bowen Theory, Systems Thinking"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                  {topicEntities.length > 1 && (
                    <button
                      onClick={() => removeTopicEntity(index)}
                      className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg"
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              onClick={addTopicEntity}
              className="mt-2 text-sm text-purple-600 hover:text-purple-700 font-medium"
            >
              + Add Topic Entity
            </button>
            <p className="text-xs text-gray-500 mt-1">
              Key topics, theories, or specialties your organization focuses on
            </p>
          </div>

          {/* Location Pool */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Location Pool * <span className="text-xs font-normal text-gray-500">(at least 1 required)</span>
            </label>
            <div className="space-y-2">
              {locationPool.map((location, index) => (
                <div key={`location-${index}-${location}`} className="flex gap-2">
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => updateLocation(index, e.target.value)}
                    placeholder="e.g., Burnaby, Richmond, Surrey"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                  {locationPool.length > 1 && (
                    <button
                      onClick={() => removeLocation(index)}
                      className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg"
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              onClick={addLocation}
              className="mt-2 text-sm text-purple-600 hover:text-purple-700 font-medium"
            >
              + Add Location
            </button>
            <p className="text-xs text-gray-500 mt-1">
              Service areas and nearby cities for geographic optimization
            </p>
          </div>

          {/* AI Model Selector */}
          {availableModels.length > 0 && (
            <div>
              <label className="block text-sm font-bold text-gray-700 mb-2">
                AI Model for GEO Analysis
              </label>
              <select
                value={selectedModel}
                onChange={(e) => handleModelChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              >
                {availableModels.map(m => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Used when running LLM-based GEO analysis from the AI Readiness tab
              </p>
            </div>
          )}

          {/* Info Box */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm font-bold text-blue-900 mb-1">How GEO Works</p>
            <p className="text-xs text-blue-800">
              GEO (Generative Engine Optimization) creates metadata that helps AI search engines (like Google AI Overviews)
              understand and cite your content. The AI will use your organization context, topic entities, and location pool
              to generate semantically rich alt text and descriptions that connect your images to high-intent searches.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 p-6 flex gap-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 bg-purple-600 text-white rounded-lg py-2 text-sm hover:bg-purple-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </div>
  )
}
