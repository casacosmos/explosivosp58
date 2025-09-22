import React, { useState, useEffect, useRef } from 'react'
import { QuickDataEntry } from './QuickDataEntry'
import { TankEditor } from './TankEditor'
import { FieldStudyInfo } from './FieldStudyInfo'

interface Props {
  apiUrl: (path: string) => string
  wsUrl: (path: string) => string
}

type WorkflowStep =
  | 'kmz_parse'
  | 'field_info'
  | 'data_entry'
  | 'processing'
  | 'hud_review'
  | 'compliance_review'
  | 'complete'

interface SessionData {
  session: string
  tanks: any[]
  hudResults: any[]
  screenshots: string[]
  complianceResults: any
  currentStep: WorkflowStep
}

export function StreamlinedApp({ apiUrl, wsUrl }: Props) {
  const [session, setSession] = useState<string>('')
  const [currentStep, setCurrentStep] = useState<WorkflowStep>('kmz_parse')
  const [data, setData] = useState<SessionData | null>(null)
  const [loading, setLoading] = useState(false)
  const [hudJob, setHudJob] = useState<any>(null)
  const [logs, setLogs] = useState<string[]>([])

  // Initialize session
  useEffect(() => {
    const stored = localStorage.getItem('session')
    if (stored) {
      setSession(stored)
      loadSessionData(stored)
    }
  }, [])

  const loadSessionData = async (sessionId: string) => {
    try {
      const res = await fetch(apiUrl(`/session/${sessionId}/datastore`))
      const store = await res.json()

      // Determine current step based on data
      let step: WorkflowStep = 'kmz_parse'
      if (store.tanks && store.tanks.length > 0) {
        step = 'data_entry'
        if (store.tanks.some((t: any) => t.hud)) {
          step = 'hud_review'
          if (store.tanks.some((t: any) => t.compliance)) {
            step = 'compliance_review'
          }
        }
      }

      setData({
        session: sessionId,
        tanks: store.tanks || [],
        hudResults: [],
        screenshots: [],
        complianceResults: null,
        currentStep: step
      })
      setCurrentStep(step)
    } catch (e) {
      console.error('Failed to load session:', e)
    }
  }

  const startNewSession = () => {
    const newSession = Date.now().toString(36) + Math.random().toString(36).substr(2)
    setSession(newSession)
    localStorage.setItem('session', newSession)
    setCurrentStep('kmz_parse')
    setData({
      session: newSession,
      tanks: [],
      hudResults: [],
      screenshots: [],
      complianceResults: null,
      currentStep: 'kmz_parse'
    })
  }

  const handleKmzUpload = async (file: File) => {
    setLoading(true)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('session', session)

    try {
      const res = await fetch(apiUrl('/kmz/parse'), { method: 'POST', body: fd })
      const json = await res.json()

      // Move to field info step
      setCurrentStep('field_info')
      await loadSessionData(session)
    } catch (e) {
      console.error('KMZ parse failed:', e)
    } finally {
      setLoading(false)
    }
  }

  const proceedToDataEntry = () => {
    setCurrentStep('data_entry')
  }

  const processData = async () => {
    setCurrentStep('processing')
    setLoading(true)

    try {
      // Step 1: Excel to JSON
      const excelRes = await fetch(apiUrl('/excel-to-json'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `session=${encodeURIComponent(session)}`
      })
      const excelJson = await excelRes.json()

      // Step 2: Run HUD
      const hudRes = await fetch(apiUrl('/hud/run'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `session=${encodeURIComponent(session)}`
      })
      const hudJson = await hudRes.json()
      setHudJob(hudJson)

      // Connect WebSocket for progress
      const ws = new WebSocket(wsUrl(`/ws/jobs/${hudJson.job_id}`))
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'log') {
          setLogs(prev => [...prev.slice(-100), msg.data])
        }
        if (msg.type === 'status' && msg.status === 'completed') {
          // HUD complete, generate PDF and move to review
          generatePdfAndProceed()
        }
      }
    } catch (e) {
      console.error('Processing failed:', e)
      setLoading(false)
    }
  }

  const generatePdfAndProceed = async () => {
    try {
      // Generate PDF
      await fetch(apiUrl('/pdf/generate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `session=${encodeURIComponent(session)}`
      })

      // Update Excel with results
      await fetch(apiUrl('/excel/update-with-results'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `session=${encodeURIComponent(session)}`
      })

      // Load updated data and move to review
      await loadSessionData(session)
      setCurrentStep('hud_review')
    } catch (e) {
      console.error('PDF generation failed:', e)
    } finally {
      setLoading(false)
    }
  }

  const approveHudResults = () => {
    setCurrentStep('compliance_review')
    runComplianceCheck()
  }

  const runComplianceCheck = async () => {
    setLoading(true)
    try {
      const res = await fetch(apiUrl('/compliance/check'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `session=${encodeURIComponent(session)}`
      })
      const json = await res.json()

      await loadSessionData(session)
      setData(prev => prev ? { ...prev, complianceResults: json } : null)
    } catch (e) {
      console.error('Compliance check failed:', e)
    } finally {
      setLoading(false)
    }
  }

  const approveCompliance = () => {
    setCurrentStep('complete')
  }

  // Step indicator
  const steps = [
    { id: 'kmz_parse', label: '1. Upload KMZ', icon: '📍' },
    { id: 'field_info', label: '2. Field Info', icon: '📋' },
    { id: 'data_entry', label: '3. Enter Data', icon: '✏️' },
    { id: 'processing', label: '4. Processing', icon: '⚙️' },
    { id: 'hud_review', label: '5. Review HUD', icon: '✅' },
    { id: 'compliance_review', label: '6. Compliance', icon: '📊' },
    { id: 'complete', label: '7. Complete', icon: '🎉' }
  ]

  const currentStepIndex = steps.findIndex(s => s.id === currentStep)

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 20, fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: 0 }}>Tank Compliance Pipeline</h1>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
          <div style={{ fontSize: '0.9em', color: '#666' }}>
            Session: {session || 'Not started'}
          </div>
          <button onClick={startNewSession} style={{ fontSize: '0.9em' }}>
            Start New Session
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative' }}>
          {/* Progress line */}
          <div style={{
            position: 'absolute',
            top: 20,
            left: 40,
            right: 40,
            height: 2,
            backgroundColor: '#e0e0e0',
            zIndex: 0
          }}>
            <div style={{
              height: '100%',
              width: `${(currentStepIndex / (steps.length - 1)) * 100}%`,
              backgroundColor: '#28a745',
              transition: 'width 0.3s ease'
            }} />
          </div>

          {/* Step indicators */}
          {steps.map((step, i) => (
            <div key={step.id} style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              position: 'relative',
              zIndex: 1
            }}>
              <div style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                backgroundColor: i <= currentStepIndex ? '#28a745' : '#e0e0e0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.2em',
                marginBottom: 8,
                transition: 'all 0.3s ease'
              }}>
                {i < currentStepIndex ? '✓' : step.icon}
              </div>
              <div style={{
                fontSize: '0.8em',
                textAlign: 'center',
                color: i <= currentStepIndex ? '#000' : '#999',
                maxWidth: 100
              }}>
                {step.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{
        backgroundColor: '#f8f9fa',
        borderRadius: 8,
        padding: 24,
        minHeight: 400
      }}>
        {/* Step 1: KMZ Upload */}
        {currentStep === 'kmz_parse' && (
          <div>
            <h2>Step 1: Upload KMZ File</h2>
            <p>Upload a KMZ/KML file containing tank locations and polygon boundaries.</p>
            <input
              type="file"
              accept=".kmz,.kml"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleKmzUpload(file)
              }}
              disabled={loading}
            />
            {loading && <div style={{ marginTop: 16 }}>Processing KMZ file...</div>}
          </div>
        )}

        {/* Step 2: Field Information */}
        {currentStep === 'field_info' && (
          <div>
            <h2>Step 2: Field Study Information</h2>
            <FieldStudyInfo session={session} apiUrl={apiUrl} />
            <div style={{ marginTop: 24, textAlign: 'right' }}>
              <button
                onClick={proceedToDataEntry}
                style={{
                  padding: '12px 24px',
                  backgroundColor: '#28a745',
                  color: 'white',
                  border: 'none',
                  borderRadius: 4,
                  fontSize: '1.1em',
                  cursor: 'pointer'
                }}
              >
                Continue to Data Entry →
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Data Entry */}
        {currentStep === 'data_entry' && (
          <div>
            <h2>Step 3: Enter Tank Data</h2>
            <QuickDataEntry session={session} apiUrl={apiUrl} />
            <div style={{ marginTop: 24, textAlign: 'right' }}>
              <button
                onClick={processData}
                disabled={loading || !data || data.tanks.length === 0}
                style={{
                  padding: '12px 24px',
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: 4,
                  fontSize: '1.1em',
                  cursor: 'pointer',
                  opacity: loading || !data || data.tanks.length === 0 ? 0.5 : 1
                }}
              >
                Process Tank Data →
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Processing */}
        {currentStep === 'processing' && (
          <div>
            <h2>Processing Tank Data</h2>
            <div style={{ marginBottom: 24 }}>
              <div>✅ Excel to JSON conversion complete</div>
              <div>{logs.length > 0 ? '🔄' : '⏳'} Running HUD calculations...</div>
              <div>⏳ Generating screenshots...</div>
              <div>⏳ Creating PDF report...</div>
            </div>

            {/* Log viewer */}
            <div style={{
              backgroundColor: '#000',
              color: '#0f0',
              padding: 12,
              borderRadius: 4,
              height: 200,
              overflowY: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.9em'
            }}>
              {logs.map((log, i) => (
                <div key={i}>{log}</div>
              ))}
            </div>
          </div>
        )}

        {/* Step 5: HUD Review */}
        {currentStep === 'hud_review' && (
          <HudReviewStep
            session={session}
            apiUrl={apiUrl}
            data={data}
            onApprove={approveHudResults}
          />
        )}

        {/* Step 6: Compliance Review */}
        {currentStep === 'compliance_review' && (
          <ComplianceReviewStep
            session={session}
            apiUrl={apiUrl}
            data={data}
            onApprove={approveCompliance}
          />
        )}

        {/* Step 7: Complete */}
        {currentStep === 'complete' && (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <div style={{ fontSize: '4em', marginBottom: 24 }}>🎉</div>
            <h2>Pipeline Complete!</h2>
            <p>All tanks have been processed and compliance has been verified.</p>
            <div style={{ marginTop: 32, display: 'flex', gap: 16, justifyContent: 'center' }}>
              <a
                href={apiUrl(`/session/${session}/export_excel`)}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  padding: '12px 24px',
                  backgroundColor: '#28a745',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: 4
                }}
              >
                📊 Download Final Excel
              </a>
              <a
                href={apiUrl(`/files/HUD_ASD_Results.pdf`)}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  padding: '12px 24px',
                  backgroundColor: '#007bff',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: 4
                }}
              >
                📄 Download PDF Report
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// HUD Results Review Component
function HudReviewStep({ session, apiUrl, data, onApprove }: any) {
  const [selectedTank, setSelectedTank] = useState(0)
  const [hudResults, setHudResults] = useState<any[]>([])
  const [screenshots, setScreenshots] = useState<string[]>([])

  useEffect(() => {
    loadHudResults()
  }, [session])

  const loadHudResults = async () => {
    try {
      // Load HUD results
      const res = await fetch(apiUrl(`/files/fast_results.json`))
      const results = await res.json()
      setHudResults(results || [])

      // Get screenshot paths
      const screenshotPaths = results.map((r: any, i: number) =>
        `/work/${session}/screenshots/tank-${String(i + 1).padStart(2, '0')}-${r.name.replace(/[^a-zA-Z0-9]/g, '-')}-${r.volume}gal.png`
      )
      setScreenshots(screenshotPaths)
    } catch (e) {
      console.error('Failed to load HUD results:', e)
    }
  }

  const currentResult = hudResults[selectedTank]
  const currentScreenshot = screenshots[selectedTank]

  return (
    <div>
      <h2>Step 5: Review HUD Results</h2>
      <p>Verify the HUD calculations against the screenshots. Check that all values are correct.</p>

      {/* Tank selector */}
      <div style={{ marginBottom: 24 }}>
        <label style={{ marginRight: 12 }}>Select Tank:</label>
        <select
          value={selectedTank}
          onChange={(e) => setSelectedTank(Number(e.target.value))}
          style={{ padding: 8, fontSize: '1.1em' }}
        >
          {hudResults.map((r, i) => (
            <option key={i} value={i}>
              {r.name} - {r.volume} gal
            </option>
          ))}
        </select>
        <span style={{ marginLeft: 12, color: '#666' }}>
          {selectedTank + 1} of {hudResults.length}
        </span>
      </div>

      {/* Side by side view */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Left: Data Table */}
        <div>
          <h3>Extracted Data</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid #ddd' }}>
                <td style={{ padding: 12, fontWeight: 'bold' }}>Tank Name</td>
                <td style={{ padding: 12 }}>{currentResult?.name}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #ddd' }}>
                <td style={{ padding: 12, fontWeight: 'bold' }}>Volume (gal)</td>
                <td style={{ padding: 12 }}>{currentResult?.volume}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #ddd' }}>
                <td style={{ padding: 12, fontWeight: 'bold' }}>Underground</td>
                <td style={{ padding: 12 }}>{currentResult?.is_underground ? 'Yes' : 'No'}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #ddd' }}>
                <td style={{ padding: 12, fontWeight: 'bold' }}>Has Dike</td>
                <td style={{ padding: 12 }}>{currentResult?.has_dike ? 'Yes' : 'No'}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #ddd', backgroundColor: '#fffacd' }}>
                <td style={{ padding: 12, fontWeight: 'bold' }}>ASDPPU (ft)</td>
                <td style={{ padding: 12, fontSize: '1.2em', fontWeight: 'bold' }}>
                  {currentResult?.results?.asdppu || 'N/A'}
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid #ddd', backgroundColor: '#fffacd' }}>
                <td style={{ padding: 12, fontWeight: 'bold' }}>ASDBPU (ft)</td>
                <td style={{ padding: 12, fontSize: '1.2em', fontWeight: 'bold' }}>
                  {currentResult?.results?.asdbpu || 'N/A'}
                </td>
              </tr>
            </tbody>
          </table>

          {/* Navigation */}
          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <button
              onClick={() => setSelectedTank(Math.max(0, selectedTank - 1))}
              disabled={selectedTank === 0}
            >
              ← Previous
            </button>
            <button
              onClick={() => setSelectedTank(Math.min(hudResults.length - 1, selectedTank + 1))}
              disabled={selectedTank === hudResults.length - 1}
            >
              Next →
            </button>
          </div>
        </div>

        {/* Right: Screenshot */}
        <div>
          <h3>HUD Calculator Screenshot</h3>
          <div style={{
            border: '1px solid #ddd',
            borderRadius: 4,
            overflow: 'hidden',
            backgroundColor: '#f0f0f0'
          }}>
            {currentScreenshot ? (
              <img
                src={apiUrl(currentScreenshot)}
                alt={`Screenshot for ${currentResult?.name}`}
                style={{ width: '100%', height: 'auto', display: 'block' }}
              />
            ) : (
              <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>
                Screenshot not available
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Approve button */}
      <div style={{ marginTop: 32, textAlign: 'right' }}>
        <button
          onClick={onApprove}
          style={{
            padding: '12px 24px',
            backgroundColor: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            fontSize: '1.1em',
            cursor: 'pointer'
          }}
        >
          ✅ Approve HUD Results & Continue →
        </button>
      </div>
    </div>
  )
}

// Compliance Review Component
function ComplianceReviewStep({ session, apiUrl, data, onApprove }: any) {
  const [complianceData, setComplianceData] = useState<any[]>([])

  useEffect(() => {
    // Load compliance results
    if (data?.complianceResults) {
      setComplianceData(data.complianceResults.tanks || [])
    }
  }, [data])

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'pass': return '#28a745'
      case 'fail': return '#dc3545'
      case 'warning': return '#ffc107'
      default: return '#6c757d'
    }
  }

  return (
    <div>
      <h2>Step 6: Compliance Review</h2>
      <p>Review compliance status for all tanks based on ASD values and distance to boundaries.</p>

      {/* Summary stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 16,
        marginBottom: 24
      }}>
        <div style={{ padding: 16, backgroundColor: '#e7f5ff', borderRadius: 8 }}>
          <div style={{ fontSize: '2em', fontWeight: 'bold' }}>
            {complianceData.length}
          </div>
          <div style={{ color: '#666' }}>Total Tanks</div>
        </div>
        <div style={{ padding: 16, backgroundColor: '#d3f9d8', borderRadius: 8 }}>
          <div style={{ fontSize: '2em', fontWeight: 'bold', color: '#28a745' }}>
            {complianceData.filter(t => t.compliance === 'Pass').length}
          </div>
          <div style={{ color: '#666' }}>Compliant</div>
        </div>
        <div style={{ padding: 16, backgroundColor: '#ffe3e3', borderRadius: 8 }}>
          <div style={{ fontSize: '2em', fontWeight: 'bold', color: '#dc3545' }}>
            {complianceData.filter(t => t.compliance === 'Fail').length}
          </div>
          <div style={{ color: '#666' }}>Non-Compliant</div>
        </div>
        <div style={{ padding: 16, backgroundColor: '#fff3cd', borderRadius: 8 }}>
          <div style={{ fontSize: '2em', fontWeight: 'bold', color: '#ffc107' }}>
            {complianceData.filter(t => t.compliance === 'Warning').length}
          </div>
          <div style={{ color: '#666' }}>Warnings</div>
        </div>
      </div>

      {/* Compliance table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <th style={{ padding: 12, textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Tank</th>
              <th style={{ padding: 12, textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Volume (gal)</th>
              <th style={{ padding: 12, textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>ASDPPU (ft)</th>
              <th style={{ padding: 12, textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Distance (ft)</th>
              <th style={{ padding: 12, textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Margin (ft)</th>
              <th style={{ padding: 12, textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {complianceData.map((tank, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #dee2e6' }}>
                <td style={{ padding: 12 }}>{tank.name}</td>
                <td style={{ padding: 12 }}>{tank.volume}</td>
                <td style={{ padding: 12 }}>{tank.asdppu || 'N/A'}</td>
                <td style={{ padding: 12 }}>{tank.distance ? tank.distance.toFixed(1) : 'N/A'}</td>
                <td style={{ padding: 12 }}>
                  {tank.distance && tank.asdppu
                    ? (tank.distance - tank.asdppu).toFixed(1)
                    : 'N/A'}
                </td>
                <td style={{ padding: 12 }}>
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: 4,
                    backgroundColor: getStatusColor(tank.compliance),
                    color: 'white',
                    fontWeight: 'bold'
                  }}>
                    {tank.compliance || 'Unknown'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Approve button */}
      <div style={{ marginTop: 32, textAlign: 'right' }}>
        <button
          onClick={onApprove}
          style={{
            padding: '12px 24px',
            backgroundColor: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            fontSize: '1.1em',
            cursor: 'pointer'
          }}
        >
          ✅ Approve Compliance Report →
        </button>
      </div>
    </div>
  )
}