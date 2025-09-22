import React, { useState, useEffect } from 'react'

interface FieldStudyProps {
  session: string
  apiUrl: (path: string) => string
}

interface Contact {
  name: string
  role?: string
  company?: string
  phone?: string
  email?: string
  notes?: string
  timestamp?: string
}

interface FieldStudy {
  date: string | null
  time: string | null
  weather: string | null
  team_lead: string | null
  team_members: string[]
  contacts: Contact[]
}

export function FieldStudyInfo({ session, apiUrl }: FieldStudyProps) {
  const [fieldStudy, setFieldStudy] = useState<FieldStudy>({
    date: null,
    time: null,
    weather: null,
    team_lead: null,
    team_members: [],
    contacts: []
  })
  const [newContact, setNewContact] = useState<Contact>({
    name: '',
    role: '',
    company: '',
    phone: '',
    email: '',
    notes: ''
  })
  const [showContactForm, setShowContactForm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [teamMemberInput, setTeamMemberInput] = useState('')

  useEffect(() => {
    if (session) loadFieldStudy()
  }, [session])

  const loadFieldStudy = async () => {
    try {
      const res = await fetch(apiUrl(`/session/${session}/field_study`))
      const data = await res.json()
      setFieldStudy({
        date: data.date || null,
        time: data.time || null,
        weather: data.weather || null,
        team_lead: data.team_lead || null,
        team_members: data.team_members || [],
        contacts: data.contacts || []
      })
    } catch (e) {
      console.error('Failed to load field study data:', e)
    }
  }

  const updateFieldStudy = async () => {
    setLoading(true)
    try {
      await fetch(apiUrl(`/session/${session}/field_study`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: fieldStudy.date,
          time: fieldStudy.time,
          weather: fieldStudy.weather,
          team_lead: fieldStudy.team_lead,
          team_members: fieldStudy.team_members
        })
      })
    } catch (e) {
      console.error('Failed to update field study:', e)
    } finally {
      setLoading(false)
    }
  }

  const addContact = async () => {
    if (!newContact.name) {
      alert('Contact name is required')
      return
    }

    setLoading(true)
    try {
      await fetch(apiUrl(`/session/${session}/contact`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newContact)
      })

      // Reload contacts
      await loadFieldStudy()

      // Clear form
      setNewContact({
        name: '',
        role: '',
        company: '',
        phone: '',
        email: '',
        notes: ''
      })
      setShowContactForm(false)
    } catch (e) {
      console.error('Failed to add contact:', e)
    } finally {
      setLoading(false)
    }
  }

  const deleteContact = async (contactName: string) => {
    if (!confirm(`Delete contact "${contactName}"?`)) return

    try {
      await fetch(apiUrl(`/session/${session}/contact/${encodeURIComponent(contactName)}`), {
        method: 'DELETE'
      })
      await loadFieldStudy()
    } catch (e) {
      console.error('Failed to delete contact:', e)
    }
  }

  const addTeamMember = () => {
    if (teamMemberInput.trim()) {
      setFieldStudy({
        ...fieldStudy,
        team_members: [...fieldStudy.team_members, teamMemberInput.trim()]
      })
      setTeamMemberInput('')
    }
  }

  const removeTeamMember = (index: number) => {
    const members = [...fieldStudy.team_members]
    members.splice(index, 1)
    setFieldStudy({ ...fieldStudy, team_members: members })
  }

  if (!session) {
    return null
  }

  return (
    <div style={{ padding: 16, border: '1px solid #ddd', borderRadius: 8, backgroundColor: '#fafafa' }}>
      <h3 style={{ marginTop: 0, marginBottom: 16 }}>📋 Field Study Information</h3>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Left Column - Study Info */}
        <div>
          <h4 style={{ marginTop: 0 }}>Study Details</h4>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'bold', fontSize: '0.9em' }}>
              Date
            </label>
            <input
              type="date"
              value={fieldStudy.date || ''}
              onChange={e => setFieldStudy({ ...fieldStudy, date: e.target.value })}
              style={{ width: '100%', padding: 6 }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'bold', fontSize: '0.9em' }}>
              Time
            </label>
            <input
              type="time"
              value={fieldStudy.time || ''}
              onChange={e => setFieldStudy({ ...fieldStudy, time: e.target.value })}
              style={{ width: '100%', padding: 6 }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'bold', fontSize: '0.9em' }}>
              Weather Conditions
            </label>
            <input
              type="text"
              value={fieldStudy.weather || ''}
              onChange={e => setFieldStudy({ ...fieldStudy, weather: e.target.value })}
              placeholder="e.g., Clear, 75°F, light wind"
              style={{ width: '100%', padding: 6 }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'bold', fontSize: '0.9em' }}>
              Team Lead
            </label>
            <input
              type="text"
              value={fieldStudy.team_lead || ''}
              onChange={e => setFieldStudy({ ...fieldStudy, team_lead: e.target.value })}
              placeholder="Lead consultant name"
              style={{ width: '100%', padding: 6 }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'bold', fontSize: '0.9em' }}>
              Team Members
            </label>
            <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
              <input
                type="text"
                value={teamMemberInput}
                onChange={e => setTeamMemberInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addTeamMember()}
                placeholder="Add team member"
                style={{ flex: 1, padding: 6 }}
              />
              <button onClick={addTeamMember}>Add</button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {fieldStudy.team_members.map((member, i) => (
                <div key={i} style={{
                  padding: '4px 8px',
                  backgroundColor: '#e9ecef',
                  borderRadius: 4,
                  fontSize: '0.9em',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}>
                  {member}
                  <button
                    onClick={() => removeTeamMember(i)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#dc3545',
                      cursor: 'pointer',
                      padding: 0,
                      fontSize: '1.2em'
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={updateFieldStudy}
            disabled={loading}
            style={{
              padding: '8px 16px',
              backgroundColor: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer'
            }}
          >
            💾 Save Study Info
          </button>
        </div>

        {/* Right Column - Contacts */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ margin: 0 }}>People Consulted</h4>
            <button onClick={() => setShowContactForm(!showContactForm)}>
              {showContactForm ? '✕ Cancel' : '+ Add Contact'}
            </button>
          </div>

          {showContactForm && (
            <div style={{
              padding: 12,
              backgroundColor: '#fff',
              border: '1px solid #dee2e6',
              borderRadius: 4,
              marginBottom: 12
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <input
                  type="text"
                  value={newContact.name}
                  onChange={e => setNewContact({ ...newContact, name: e.target.value })}
                  placeholder="Name *"
                  style={{ padding: 6 }}
                />
                <input
                  type="text"
                  value={newContact.role || ''}
                  onChange={e => setNewContact({ ...newContact, role: e.target.value })}
                  placeholder="Role/Title"
                  style={{ padding: 6 }}
                />
                <input
                  type="text"
                  value={newContact.company || ''}
                  onChange={e => setNewContact({ ...newContact, company: e.target.value })}
                  placeholder="Company/Organization"
                  style={{ padding: 6 }}
                />
                <input
                  type="tel"
                  value={newContact.phone || ''}
                  onChange={e => setNewContact({ ...newContact, phone: e.target.value })}
                  placeholder="Phone"
                  style={{ padding: 6 }}
                />
                <input
                  type="email"
                  value={newContact.email || ''}
                  onChange={e => setNewContact({ ...newContact, email: e.target.value })}
                  placeholder="Email"
                  style={{ padding: 6, gridColumn: 'span 2' }}
                />
                <textarea
                  value={newContact.notes || ''}
                  onChange={e => setNewContact({ ...newContact, notes: e.target.value })}
                  placeholder="Notes (tank owner, site manager, etc.)"
                  rows={2}
                  style={{ padding: 6, gridColumn: 'span 2' }}
                />
              </div>
              <button
                onClick={addContact}
                disabled={loading || !newContact.name}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer'
                }}
              >
                Add Contact
              </button>
            </div>
          )}

          <div style={{ maxHeight: 300, overflowY: 'auto' }}>
            {fieldStudy.contacts.length === 0 ? (
              <div style={{ color: '#666', fontSize: '0.9em', fontStyle: 'italic' }}>
                No contacts added yet
              </div>
            ) : (
              fieldStudy.contacts.map((contact, i) => (
                <div key={i} style={{
                  padding: 8,
                  marginBottom: 8,
                  backgroundColor: '#fff',
                  border: '1px solid #dee2e6',
                  borderRadius: 4,
                  fontSize: '0.9em'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <strong>{contact.name}</strong>
                    <button
                      onClick={() => deleteContact(contact.name)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#dc3545',
                        cursor: 'pointer',
                        padding: 0
                      }}
                    >
                      🗑️
                    </button>
                  </div>
                  {contact.role && <div>Role: {contact.role}</div>}
                  {contact.company && <div>Company: {contact.company}</div>}
                  {contact.phone && <div>Phone: {contact.phone}</div>}
                  {contact.email && <div>Email: {contact.email}</div>}
                  {contact.notes && (
                    <div style={{ marginTop: 4, fontStyle: 'italic', color: '#666' }}>
                      {contact.notes}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}