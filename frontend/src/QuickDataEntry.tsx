import React, { useState, useRef, useEffect } from 'react'

interface QuickEntryProps {
  session: string
  apiUrl: (path: string) => string
  onComplete?: () => void
}

interface TankEntry {
  name: string
  volume: string
  type: string
  diameter: string
  height: string
  length: string
  width: string
  underground: boolean
  hasDike: boolean
  dikeLength: string
  dikeWidth: string
  notes: string
}

const TANK_TYPES = ['UST', 'AST', 'LPG', 'Diesel', 'Gasoline', 'Pressurized', 'Storage']

export function QuickDataEntry({ session, apiUrl, onComplete }: QuickEntryProps) {
  const [entries, setEntries] = useState<TankEntry[]>([])
  const [currentEntry, setCurrentEntry] = useState<TankEntry>(getEmptyEntry())
  const [activeField, setActiveField] = useState<string>('name')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [tanks, setTanks] = useState<any[]>([])
  const [selectedTankIndex, setSelectedTankIndex] = useState(0)

  // Refs for input fields
  const nameRef = useRef<HTMLInputElement>(null)
  const volumeRef = useRef<HTMLInputElement>(null)
  const typeRef = useRef<HTMLInputElement>(null)
  const diameterRef = useRef<HTMLInputElement>(null)
  const heightRef = useRef<HTMLInputElement>(null)

  function getEmptyEntry(): TankEntry {
    return {
      name: '',
      volume: '',
      type: '',
      diameter: '',
      height: '',
      length: '',
      width: '',
      underground: false,
      hasDike: false,
      dikeLength: '',
      dikeWidth: '',
      notes: ''
    }
  }

  // Load existing tanks
  useEffect(() => {
    if (session) loadTanks()
  }, [session])

  const loadTanks = async () => {
    try {
      const res = await fetch(apiUrl(`/session/${session}/tanks`))
      const data = await res.json()
      setTanks(data.tanks || [])

      // Pre-populate current entry with first tank if available
      if (data.tanks && data.tanks.length > 0) {
        populateFromTank(data.tanks[0])
      }
    } catch (e) {
      console.error('Failed to load tanks:', e)
    }
  }

  const populateFromTank = (tank: any) => {
    setCurrentEntry({
      name: tank.name || '',
      volume: tank.volume_gal ? tank.volume_gal.toString() : '',
      type: tank.type || '',
      diameter: tank.measurements?.diameter_ft || '',
      height: tank.measurements?.height_ft || '',
      length: tank.measurements?.length_ft || '',
      width: tank.measurements?.width_ft || '',
      underground: tank.type === 'UST',
      hasDike: tank.has_dike || false,
      dikeLength: tank.dike_dims?.[0] || '',
      dikeWidth: tank.dike_dims?.[1] || '',
      notes: ''
    })
  }

  // Smart parsing for volume input (handles "5000 gal", "5000gal", "5,000", etc.)
  const parseVolume = (input: string): number | null => {
    const cleaned = input.replace(/[^\d.]/g, '')
    const volume = parseFloat(cleaned)
    return isNaN(volume) ? null : volume
  }

  // Smart parsing for dimensions (handles "10 ft", "10'", "10", etc.)
  const parseDimension = (input: string): number | null => {
    const cleaned = input.replace(/[^\d.]/g, '')
    const dim = parseFloat(cleaned)
    return isNaN(dim) ? null : dim
  }

  // Quick save current entry
  const saveCurrentEntry = async () => {
    if (!currentEntry.name) {
      setMessage('Tank name required')
      return
    }

    setLoading(true)
    try {
      const tankData = {
        name: currentEntry.name,
        volume_gal: parseVolume(currentEntry.volume),
        type: currentEntry.type || (currentEntry.underground ? 'UST' : 'AST'),
        has_dike: currentEntry.hasDike,
        dike_dims: currentEntry.hasDike && currentEntry.dikeLength && currentEntry.dikeWidth
          ? [parseDimension(currentEntry.dikeLength), parseDimension(currentEntry.dikeWidth)]
          : null,
        measurements: {
          ...(currentEntry.diameter && { diameter_ft: parseDimension(currentEntry.diameter) }),
          ...(currentEntry.height && { height_ft: parseDimension(currentEntry.height) }),
          ...(currentEntry.length && { length_ft: parseDimension(currentEntry.length) }),
          ...(currentEntry.width && { width_ft: parseDimension(currentEntry.width) })
        }
      }

      // Check if tank exists
      const existingTank = tanks.find(t => t.name.toLowerCase() === currentEntry.name.toLowerCase())

      if (existingTank) {
        // Update existing
        await fetch(apiUrl(`/session/${session}/tank/${encodeURIComponent(currentEntry.name)}`), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tankData)
        })
        setMessage(`Updated: ${currentEntry.name}`)
      } else {
        // Create new
        await fetch(apiUrl(`/session/${session}/tank`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tankData)
        })
        setMessage(`Added: ${currentEntry.name}`)
      }

      // Move to next tank
      await loadTanks()
      moveToNextTank()

    } catch (e) {
      setMessage('Save failed')
    } finally {
      setLoading(false)
    }
  }

  const moveToNextTank = () => {
    if (selectedTankIndex < tanks.length - 1) {
      const nextIndex = selectedTankIndex + 1
      setSelectedTankIndex(nextIndex)
      populateFromTank(tanks[nextIndex])
      nameRef.current?.focus()
    } else {
      // Clear for new entry
      setCurrentEntry(getEmptyEntry())
      setMessage('All tanks processed!')
      nameRef.current?.focus()
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+Enter or Cmd+Enter to save
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        saveCurrentEntry()
      }

      // Tab navigation handled by browser

      // Ctrl+N for next tank
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        moveToNextTank()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentEntry, tanks, selectedTankIndex])

  // Bulk paste handler
  const handleBulkPaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      const lines = text.split('\n').map(l => l.trim()).filter(l => l)

      // Try to parse as tab-delimited or comma-delimited
      for (const line of lines) {
        const parts = line.includes('\t') ? line.split('\t') : line.split(',')

        if (parts.length >= 2) {
          const [name, volume, type, ...dims] = parts

          const tankData = {
            name: name.trim(),
            volume_gal: parseVolume(volume),
            type: type?.trim() || 'AST',
            measurements: dims.length >= 2 ? {
              diameter_ft: parseDimension(dims[0]),
              height_ft: parseDimension(dims[1])
            } : null
          }

          await fetch(apiUrl(`/session/${session}/tank`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tankData)
          })
        }
      }

      setMessage(`Imported ${lines.length} entries`)
      await loadTanks()
    } catch (e) {
      setMessage('Paste failed - check clipboard')
    }
  }

  return (
    <div style={{ padding: 16, border: '1px solid #ddd', borderRadius: 8, backgroundColor: '#f9f9f9' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>⚡ Quick Data Entry</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{ color: '#666', fontSize: '0.9em' }}>
            Tank {selectedTankIndex + 1} of {tanks.length || '?'}
          </span>
          <button onClick={handleBulkPaste}>📋 Paste Bulk</button>
          <button onClick={loadTanks}>🔄 Refresh</button>
        </div>
      </div>

      {message && (
        <div style={{
          padding: 8,
          marginBottom: 16,
          backgroundColor: message.includes('failed') ? '#fee' : '#efe',
          borderRadius: 4,
          color: message.includes('failed') ? '#c00' : '#060'
        }}>
          {message}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Left Column - Basic Info */}
        <div>
          <h4 style={{ marginTop: 0, marginBottom: 12 }}>Tank Information</h4>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em', fontWeight: 'bold' }}>
              Tank Name/ID *
            </label>
            <input
              ref={nameRef}
              type="text"
              value={currentEntry.name}
              onChange={e => setCurrentEntry({ ...currentEntry, name: e.target.value })}
              onFocus={() => setActiveField('name')}
              placeholder="e.g., Tank-01, UST-1"
              style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '2px solid #ddd' }}
              autoFocus
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em', fontWeight: 'bold' }}>
              Volume (gallons)
            </label>
            <input
              ref={volumeRef}
              type="text"
              value={currentEntry.volume}
              onChange={e => setCurrentEntry({ ...currentEntry, volume: e.target.value })}
              onFocus={() => setActiveField('volume')}
              placeholder="e.g., 5000, 5000 gal"
              style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '2px solid #ddd' }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em', fontWeight: 'bold' }}>
              Tank Type
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                ref={typeRef}
                type="text"
                value={currentEntry.type}
                onChange={e => setCurrentEntry({ ...currentEntry, type: e.target.value })}
                onFocus={() => setActiveField('type')}
                placeholder="UST, AST, LPG..."
                list="tank-types"
                style={{ flex: 1, padding: 8, fontSize: '1.1em', border: '2px solid #ddd' }}
              />
              <datalist id="tank-types">
                {TANK_TYPES.map(t => <option key={t} value={t} />)}
              </datalist>
            </div>
          </div>

          <div style={{ marginBottom: 12, display: 'flex', gap: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={currentEntry.underground}
                onChange={e => setCurrentEntry({ ...currentEntry, underground: e.target.checked })}
                style={{ width: 20, height: 20 }}
              />
              <span style={{ fontWeight: 'bold' }}>Underground</span>
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={currentEntry.hasDike}
                onChange={e => setCurrentEntry({ ...currentEntry, hasDike: e.target.checked })}
                style={{ width: 20, height: 20 }}
              />
              <span style={{ fontWeight: 'bold' }}>Has Dike</span>
            </label>
          </div>
        </div>

        {/* Right Column - Dimensions */}
        <div>
          <h4 style={{ marginTop: 0, marginBottom: 12 }}>Dimensions (feet)</h4>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em' }}>
                Diameter
              </label>
              <input
                ref={diameterRef}
                type="text"
                value={currentEntry.diameter}
                onChange={e => setCurrentEntry({ ...currentEntry, diameter: e.target.value })}
                placeholder="10, 10 ft"
                style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '1px solid #ddd' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em' }}>
                Height
              </label>
              <input
                ref={heightRef}
                type="text"
                value={currentEntry.height}
                onChange={e => setCurrentEntry({ ...currentEntry, height: e.target.value })}
                placeholder="12, 12'"
                style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '1px solid #ddd' }}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em' }}>
                Length
              </label>
              <input
                type="text"
                value={currentEntry.length}
                onChange={e => setCurrentEntry({ ...currentEntry, length: e.target.value })}
                placeholder="20"
                style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '1px solid #ddd' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em' }}>
                Width
              </label>
              <input
                type="text"
                value={currentEntry.width}
                onChange={e => setCurrentEntry({ ...currentEntry, width: e.target.value })}
                placeholder="15"
                style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '1px solid #ddd' }}
              />
            </div>
          </div>

          {currentEntry.hasDike && (
            <>
              <h5 style={{ marginBottom: 8 }}>Dike Dimensions</h5>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em' }}>
                    Dike Length
                  </label>
                  <input
                    type="text"
                    value={currentEntry.dikeLength}
                    onChange={e => setCurrentEntry({ ...currentEntry, dikeLength: e.target.value })}
                    placeholder="25"
                    style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '1px solid #ddd' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em' }}>
                    Dike Width
                  </label>
                  <input
                    type="text"
                    value={currentEntry.dikeWidth}
                    onChange={e => setCurrentEntry({ ...currentEntry, dikeWidth: e.target.value })}
                    placeholder="20"
                    style={{ width: '100%', padding: 8, fontSize: '1.1em', border: '1px solid #ddd' }}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Notes field */}
      <div style={{ marginTop: 16 }}>
        <label style={{ display: 'block', marginBottom: 4, fontSize: '0.9em' }}>
          Notes (optional)
        </label>
        <textarea
          value={currentEntry.notes}
          onChange={e => setCurrentEntry({ ...currentEntry, notes: e.target.value })}
          placeholder="Any additional observations..."
          rows={2}
          style={{ width: '100%', padding: 8, border: '1px solid #ddd' }}
        />
      </div>

      {/* Action buttons */}
      <div style={{ marginTop: 16, display: 'flex', gap: 8, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={saveCurrentEntry}
            disabled={loading || !currentEntry.name}
            style={{
              padding: '10px 20px',
              backgroundColor: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              fontSize: '1.1em',
              cursor: 'pointer'
            }}
          >
            💾 Save & Next (Ctrl+Enter)
          </button>

          <button
            onClick={() => setCurrentEntry(getEmptyEntry())}
            disabled={loading}
            style={{ padding: '10px 20px' }}
          >
            Clear
          </button>

          <button
            onClick={moveToNextTank}
            disabled={loading || selectedTankIndex >= tanks.length - 1}
            style={{ padding: '10px 20px' }}
          >
            Skip →
          </button>
        </div>

        <div style={{ color: '#666', fontSize: '0.9em', alignSelf: 'center' }}>
          <strong>Tips:</strong> Tab to move between fields | Ctrl+Enter to save | Ctrl+N for next
        </div>
      </div>

      {/* Quick reference */}
      <details style={{ marginTop: 16 }}>
        <summary style={{ cursor: 'pointer', color: '#666' }}>📋 Bulk Paste Format</summary>
        <pre style={{ fontSize: '0.85em', backgroundColor: '#f5f5f5', padding: 8, marginTop: 8 }}>
{`Tank-01	5000	UST	10	12
Tank-02	8000	AST	15	10
Tank-03	2500	LPG	8	8

Or comma-separated:
Tank-01,5000,UST,10,12`}
        </pre>
      </details>
    </div>
  )
}