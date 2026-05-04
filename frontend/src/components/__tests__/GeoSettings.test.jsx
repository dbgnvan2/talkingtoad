import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import GeoSettings from '../GeoSettings.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('GeoSettings', () => {
  const mockDomain = 'example.com'

  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation((url) => {
      if (url.includes('/geo/settings')) {
        return mockFetchResponse({
          org_name: 'Example Corp',
          topic_entities: ['Web Development', 'SEO'],
          primary_location: 'San Francisco',
          location_pool: ['San Francisco', 'Oakland', 'Berkeley'],
          model: 'gemini-1.5-pro',
          temperature: 0.4,
          max_tokens: 500,
          client_name: 'Example Corp',
          prepared_by: 'John Doe',
        })
      }
      return mockFetchResponse({})
    })
  })

  it('renders GEO settings modal when open', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByText('GEO Settings')).toBeInTheDocument()
    })
  })

  it('does not render when closed', () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={false} onClose={vi.fn()} />
    )

    expect(screen.queryByText('GEO Settings')).not.toBeInTheDocument()
  })

  it('loads and displays configuration', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByDisplayValue('Example Corp')).toBeInTheDocument()
      expect(screen.getByDisplayValue('San Francisco')).toBeInTheDocument()
    })
  })

  it('displays topic entities as tags', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByText('Web Development')).toBeInTheDocument()
      expect(screen.getByText('SEO')).toBeInTheDocument()
    })
  })

  it('displays location pool items as tags', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByText('Oakland')).toBeInTheDocument()
      expect(screen.getByText('Berkeley')).toBeInTheDocument()
    })
  })

  it('allows removing topic entities', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByText('Web Development')).toBeInTheDocument()
    })

    const removeButtons = screen.getAllByText('×')
    fireEvent.click(removeButtons[0])

    await waitFor(() => {
      expect(screen.queryByText('Web Development')).not.toBeInTheDocument()
    })
  })

  it('allows removing locations', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByText('Oakland')).toBeInTheDocument()
    })

    const removeButtons = screen.getAllByText('×')
    fireEvent.click(removeButtons[removeButtons.length - 1])

    await waitFor(() => {
      expect(screen.queryByText('Oakland')).not.toBeInTheDocument()
    })
  })

  it('allows editing organization name', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      const orgInput = screen.getByDisplayValue('Example Corp')
      fireEvent.change(orgInput, { target: { value: 'New Corp Name' } })
      expect(orgInput.value).toBe('New Corp Name')
    })
  })

  it('allows changing AI model', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      const modelSelect = screen.getByDisplayValue('gemini-1.5-pro')
      fireEvent.change(modelSelect, { target: { value: 'gpt-4o' } })
      expect(modelSelect.value).toBe('gpt-4o')
    })
  })

  it('displays temperature slider', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      const temperatureSlider = screen.getByDisplayValue('0.4')
      expect(temperatureSlider).toHaveAttribute('type', 'range')
    })
  })

  it('allows saving configuration', async () => {
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByText('Save Configuration')).toBeInTheDocument()
    })

    const saveButton = screen.getByText('Save Configuration')
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/geo/settings'),
        expect.objectContaining({ method: 'POST' })
      )
    })
  })

  it('shows close button', async () => {
    const mockOnClose = vi.fn()
    renderWithProviders(
      <GeoSettings domain={mockDomain} isOpen={true} onClose={mockOnClose} />
    )

    await waitFor(() => {
      const closeButton = screen.getByText('×')
      fireEvent.click(closeButton)
      expect(mockOnClose).toHaveBeenCalled()
    })
  })
})
