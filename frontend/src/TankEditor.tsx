import React, { useState, useEffect } from 'react'

interface Tank {
  id: number
  name: string
  volume_gal: number | null
  type: string | null
  has_dike: boolean | null
  dike_dims: [number, number] | null
  measurements: {
    length_ft?: number
    width_ft?: number
    height_ft?: number
    diameter_ft?: number
  } | null
  coords: {
    lat: number
    lon: number
  } | null
}

interface TankEditorProps {
  session: string
  apiUrl: (path: string) => string
  onUpdate?: () => void
}

export function TankEditor({ session, apiUrl, onUpdate }: TankEditorProps) {
  const [tanks, setTanks] = useState<Tank[]>([])
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editData, setEditData] = useState<Partial<Tank>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')

  // Load tanks on mount or session change
  useEffect(() => {
    if (session) loadTanks()
  }, [session])

  const loadTanks = async () => {
    if (!session) return
    setLoading(true)
    try {
      const res = await fetch(apiUrl(`/session/${session}/tanks`))
      const data = await res.json()
      setTanks(data.tanks || [])
      setError('')
    } catch (e) {
      setError('Failed to load tanks')
    } finally {
      setLoading(false)
    }
  }

  const startEdit = (tank: Tank) => {
    setEditingId(tank.id)
    setEditData({
      name: tank.name,
      volume_gal: tank.volume_gal,
      type: tank.type,
      has_dike: tank.has_dike,
      dike_dims: tank.dike_dims,
      measurements: tank.measurements ? { ...tank.measurements } : null,
      coords: tank.coords ? { ...tank.coords } : null
    })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditData({})
  }

  const saveEdit = async () => {
    if (!editingId) return

    const tank = tanks.find(t => t.id === editingId)
    if (!tank) return

    setLoading(true)
    try {
      const res = await fetch(apiUrl(`/session/${session}/tank/${encodeURIComponent(tank.name)}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editData)
      })

      if (res.ok) {
        await loadTanks()
        cancelEdit()
        if (onUpdate) onUpdate()
      } else {
        setError('Failed to update tank')
      }
    } catch (e) {
      setError('Update error')
    } finally {
      setLoading(false)
    }
  }

  const addTank = async () => {
    const newTank = {
      name: `Tank-${tanks.length + 1}`,
      volume_gal: null,
      type: 'UST',
      has_dike: false,
      measurements: { diameter_ft: 10, height_ft: 10 }
    }

    setLoading(true)
    try {
      const res = await fetch(apiUrl(`/session/${session}/tank`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTank)
      })

      if (res.ok) {
        await loadTanks()
        if (onUpdate) onUpdate()
      }
    } catch (e) {
      setError('Failed to add tank')
    } finally {
      setLoading(false)
    }
  }

  const deleteTank = async (tankName: string) => {
    if (!confirm(`Delete tank "${tankName}"?`)) return

    setLoading(true)
    try {
      const res = await fetch(apiUrl(`/session/${session}/tank/${encodeURIComponent(tankName)}`), {
        method: 'DELETE'
      })

      if (res.ok) {
        await loadTanks()
        if (onUpdate) onUpdate()
      }
    } catch (e) {
      setError('Failed to delete tank')
    } finally {
      setLoading(false)
    }
  }

  const bulkSave = async () => {
    setLoading(true)
    try {
      const res = await fetch(apiUrl(`/session/${session}/tanks/bulk_update`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(tanks)
      })

      if (res.ok) {
        alert('All tanks saved successfully')
        if (onUpdate) onUpdate()
      }
    } catch (e) {
      setError('Failed to save all tanks')
    } finally {
      setLoading(false)
    }
  }

  const exportToExcel = () => {
    window.open(apiUrl(`/session/${session}/export_excel`), '_blank')
  }

  if (!session) {
    return <div style={{ padding: 16, color: '#666' }}>No session active. Parse KMZ first.</div>
  }

  return (
    <div style={{ padding: 16, border: '1px solid #ddd', borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>Tank Data Editor</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={loadTanks} disabled={loading}>Refresh</button>
          <button onClick={addTank} disabled={loading}>Add Tank</button>
          <button onClick={bulkSave} disabled={loading}>Save All</button>
          <button onClick={exportToExcel} disabled={loading}>Export Excel</button>
        </div>
      </div>

      {error && (
        <div style={{ color: 'red', marginBottom: 16 }}>{error}</div>
      )}

      {loading && <div>Loading...</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f5f5f5' }}>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>ID</th>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>Name</th>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>Volume (gal)</th>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>Type</th>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>Has Dike</th>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>Dimensions</th>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>Coordinates</th>
              <th style={{ padding: 8, textAlign: 'left', border: '1px solid #ddd' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {tanks.map(tank => (
              <tr key={tank.id}>
                <td style={{ padding: 8, border: '1px solid #ddd' }}>{tank.id}</td>
                <td style={{ padding: 8, border: '1px solid #ddd' }}>
                  {editingId === tank.id ? (
                    <input
                      value={editData.name || ''}
                      onChange={e => setEditData({ ...editData, name: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  ) : (
                    tank.name
                  )}
                </td>
                <td style={{ padding: 8, border: '1px solid #ddd' }}>
                  {editingId === tank.id ? (
                    <input
                      type="number"
                      value={editData.volume_gal || ''}
                      onChange={e => setEditData({ ...editData, volume_gal: parseFloat(e.target.value) || null })}
                      style={{ width: '100%' }}
                    />
                  ) : (
                    tank.volume_gal || '-'
                  )}
                </td>
                <td style={{ padding: 8, border: '1px solid #ddd' }}>
                  {editingId === tank.id ? (
                    <select
                      value={editData.type || ''}
                      onChange={e => setEditData({ ...editData, type: e.target.value })}
                      style={{ width: '100%' }}
                    >
                      <option value="">-</option>
                      <option value="UST">UST</option>
                      <option value="AST">AST</option>
                      <option value="LPG">LPG</option>
                      <option value="Pressurized">Pressurized</option>
                    </select>
                  ) : (
                    tank.type || '-'
                  )}
                </td>
                <td style={{ padding: 8, border: '1px solid #ddd' }}>
                  {editingId === tank.id ? (
                    <input
                      type="checkbox"
                      checked={editData.has_dike || false}
                      onChange={e => setEditData({ ...editData, has_dike: e.target.checked })}
                    />
                  ) : (
                    tank.has_dike ? 'Yes' : 'No'
                  )}
                </td>
                <td style={{ padding: 8, border: '1px solid #ddd' }}>
                  {editingId === tank.id ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <input
                        type="number"
                        placeholder="Diameter (ft)"
                        value={editData.measurements?.diameter_ft || ''}
                        onChange={e => setEditData({
                          ...editData,
                          measurements: {
                            ...editData.measurements,
                            diameter_ft: parseFloat(e.target.value) || undefined
                          }
                        })}
                        style={{ width: 100 }}
                      />
                      <input
                        type="number"
                        placeholder="Height (ft)"
                        value={editData.measurements?.height_ft || ''}
                        onChange={e => setEditData({
                          ...editData,
                          measurements: {
                            ...editData.measurements,
                            height_ft: parseFloat(e.target.value) || undefined
                          }
                        })}
                        style={{ width: 100 }}
                      />
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.9em' }}>
                      {tank.measurements ? (
                        <>
                          {tank.measurements.diameter_ft && `D: ${tank.measurements.diameter_ft}ft`}
                          {tank.measurements.height_ft && ` H: ${tank.measurements.height_ft}ft`}
                          {tank.measurements.length_ft && `L: ${tank.measurements.length_ft}ft`}
                          {tank.measurements.width_ft && ` W: ${tank.measurements.width_ft}ft`}
                        </>
                      ) : '-'}
                    </div>
                  )}
                </td>
                <td style={{ padding: 8, border: '1px solid #ddd', fontSize: '0.9em' }}>
                  {tank.coords ? `${tank.coords.lat.toFixed(5)}, ${tank.coords.lon.toFixed(5)}` : '-'}
                </td>
                <td style={{ padding: 8, border: '1px solid #ddd' }}>
                  {editingId === tank.id ? (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={saveEdit} disabled={loading}>Save</button>
                      <button onClick={cancelEdit} disabled={loading}>Cancel</button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={() => startEdit(tank)} disabled={loading}>Edit</button>
                      <button onClick={() => deleteTank(tank.name)} disabled={loading}>Delete</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {tanks.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: 32, color: '#666' }}>
          No tanks found. Add tanks or parse an Excel file.
        </div>
      )}
    </div>
  )
}