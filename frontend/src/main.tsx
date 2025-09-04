import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'

// API base resolution: prefer env; fallback to '/api' under current origin for dev proxy
const API_BASE: string = (import.meta as any).env?.VITE_API_BASE || `${window.location.origin}/api`

function joinUrl(base: string, path: string): string {
  if (!base) return path
  if (path.startsWith('http')) return path
  const b = base.endsWith('/') ? base.slice(0, -1) : base
  const p = path.startsWith('/') ? path : `/${path}`
  return `${b}${p}`
}

function apiUrl(path: string): string {
  return joinUrl(API_BASE, path)
}

function wsBaseFromApiBase(): string {
  try {
    const url = new URL(API_BASE, window.location.origin)
    const proto = url.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${url.host}`
  } catch {
    // Fallback: use window location
    return window.location.protocol === 'https:' ? 'wss://' + window.location.host : 'ws://' + window.location.host
  }
}

function wsUrl(path: string): string {
  return joinUrl(wsBaseFromApiBase(), path)
}

function fileHrefFromOutputPath(p: string): string {
  // Accept absolute output path or already-relative path under output/
  const rel = p.includes('/output/') ? p.split('/output/')[1] : p
  return apiUrl(`/files/${rel}`)
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8, marginBottom: 16 }}>
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      {children}
    </section>
  )
}

function useSessionState() {
  const [session, setSession] = useState('')
  useEffect(() => {
    setSession(localStorage.getItem('session') || '')
  }, [])
  const set = (s: string) => {
    setSession(s)
    localStorage.setItem('session', s)
  }
  return { session, setSession: set }
}

function KmzParse() {
  const { session, setSession } = useSessionState()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [out, setOut] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string>("")
  const [pickerOpen, setPickerOpen] = useState(false)
  const [sessionFiles, setSessionFiles] = useState<string[]>([])
  const [selected, setSelected] = useState<Record<string, boolean>>({})

  const submit = async () => {
    const f = inputRef.current?.files?.[0]
    if (!f) return
    setBusy(true); setStatus('Uploading KMZ and parsing…')
    const fd = new FormData()
    fd.append('file', f)
    if (session) fd.append('session', session)
    try {
      const res = await fetch(apiUrl('/kmz/parse'), { method: 'POST', body: fd })
      const json = await res.json()
      setOut(json)
      if (json.session) setSession(json.session)
      setStatus(`Done. Polygons: ${json.polygons_count || 0} | Points: ${json.points_count || 0}`)
      // Store relative paths for session downloads
      const files: string[] = (json.files || []).map((f: string) => (f.indexOf('/output/') >= 0 ? f.split('/output/')[1] : f))
      setSessionFiles(files)
      const initSel: Record<string, boolean> = {}
      files.forEach(fp => { initSel[fp] = true })
      setSelected(initSel)
    } catch (e) {
      setStatus('Error parsing KMZ')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="KMZ → Parse (Agent)">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="file" accept=".kmz,.kml" ref={inputRef} />
        <button disabled={busy} onClick={submit}>Parse</button>
        {status && <small>{status}</small>}
      </div>
      {out && (
        <div style={{ marginTop: 8 }}>
          <div>Session: {out.session}</div>
          <button onClick={() => setPickerOpen(v => !v)} style={{ marginTop: 8 }}>
            {pickerOpen ? 'Hide downloads' : 'Download files'}
          </button>
          {pickerOpen && (
            <div style={{ marginTop: 8, border: '1px solid #eee', padding: 8, borderRadius: 6 }}>
              <div style={{ marginBottom: 8 }}>
                <button onClick={() => {
                  const all: Record<string, boolean> = {}
                  sessionFiles.forEach(fp => { all[fp] = true })
                  setSelected(all)
                }}>Select all</button>
                <button style={{ marginLeft: 8 }} onClick={() => {
                  const none: Record<string, boolean> = {}
                  sessionFiles.forEach(fp => { none[fp] = false })
                  setSelected(none)
                }}>Select none</button>
                <button style={{ marginLeft: 8 }} onClick={() => {
                  // trigger downloads
                  Object.keys(selected).forEach(fp => {
                    if (selected[fp]) {
                      const a = document.createElement('a')
                      a.href = fileHrefFromOutputPath(fp)
                      a.download = fp.split('/').pop() || 'download'
                      a.target = '_blank'
                      document.body.appendChild(a)
                      a.click()
                      document.body.removeChild(a)
                    }
                  })
                }}>Download selected</button>
              </div>
              <div style={{ maxHeight: 200, overflow: 'auto' }}>
                {sessionFiles.map(fp => (
                  <label key={fp} style={{ display: 'block' }}>
                    <input type="checkbox" checked={!!selected[fp]} onChange={e => setSelected(s => ({ ...s, [fp]: e.target.checked }))} />
                    <span style={{ marginLeft: 8 }}>{fp.split('/').pop()}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Section>
  )
}

function ExcelToJson({ onValidated }: { onValidated: (ok: boolean, preview?: any) => void }) {
  const { session, setSession } = useSessionState()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<any>(null)
  const [message, setMessage] = useState<string>('')
  const [status, setStatus] = useState<string>("")
  const [jsonReady, setJsonReady] = useState<boolean>(false)
  const [tanksCount, setTanksCount] = useState<number>(0)
  const [hudInputReady, setHudInputReady] = useState<{count:number,path:string}|null>(null)
  const [preserveCols, setPreserveCols] = useState(true)
  const [writeNormalizedCopy, setWriteNormalizedCopy] = useState(false)
  const [normReport, setNormReport] = useState<any>(null)
  const [normalizedCopyPath, setNormalizedCopyPath] = useState<string | null>(null)
  const [manualAck, setManualAck] = useState<boolean>(false)

  useEffect(() => {
    const key = session ? `manualExcelAck:${session}` : 'manualExcelAck'
    const v = (typeof localStorage !== 'undefined') ? localStorage.getItem(key) : null
    setManualAck(v === '1')
  }, [session])

  const submit = async () => {
    if (!manualAck) { setStatus('Acknowledge manual Excel step above'); return }
    setBusy(true); setStatus('Uploading Excel and validating…')
    const f = inputRef.current?.files?.[0]
    const fd = new FormData()
    if (f) fd.append('file', f)
    if (session) fd.append('session', session)
    fd.append('preserve_columns', String(preserveCols))
    fd.append('normalize_copy', String(writeNormalizedCopy))
    try {
      const res = await fetch(apiUrl('/excel-to-json'), { method: 'POST', body: fd })
      const json = await res.json()
      if (json.session) setSession(json.session)
      setPreview(json.preview)
      setMessage(json.validated ? 'Verification done' : 'Verification failed')
      onValidated(!!json.validated, json.preview)
      setStatus('Ready')
      setJsonReady(!!json.validated)
      setTanksCount(json.tanks_count || (json.json && json.json.tanks ? json.json.tanks.length : 0) || 0)
      // Precompute HUD input filtered config so user can review before run
      if (json.validated && (json.session || session)) {
        try {
          const resp = await fetch(apiUrl('/config/prepare_hud_input'), { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: `session=${encodeURIComponent(json.session || session)}` })
          const ji = await resp.json()
          if (ji && ji.ok) setHudInputReady({ count: ji.count || 0, path: ji.path })
        } catch {}
      }
    } catch (e) {
      setMessage('Verification failed')
      setStatus('Error during validation')
      onValidated(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="Excel → JSON (validated)">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="file" accept=".xlsx,.xls" ref={inputRef} />
        <button disabled={busy || !manualAck} onClick={submit} title={!manualAck ? 'Confirm manual Excel step above' : 'Convert + Verify'}>Convert + Verify</button>
        {message && <span>{message}</span>}
        {status && <small style={{ marginLeft: 8, color: '#555' }}>{status}</small>}
        {jsonReady && session && (
          <a style={{ marginLeft: 12 }} href={apiUrl(`/config/json?session=${session}`)} target="_blank" rel="noopener noreferrer" download>
            Download JSON
          </a>
        )}
        {jsonReady && (
          <small style={{ marginLeft: 12, color: '#555' }}>Tanks: {tanksCount}</small>
        )}
        {hudInputReady && session && (
          <a style={{ marginLeft: 12 }} href={apiUrl(`/config/hud_input?session=${session}`)} target="_blank" rel="noopener noreferrer" download>
            Download HUD Input ({hudInputReady.count})
          </a>
        )}
      </div>
      {!manualAck && (
        <div style={{ marginTop: 8 }}>
          <small style={{ color: '#a00' }}>Please complete and acknowledge the manual Excel step above to enable conversion.</small>
        </div>
      )}
      <div style={{ marginTop: 8 }}>
        <label style={{ marginRight: 12 }}>
          <input type="checkbox" checked={preserveCols} onChange={e => setPreserveCols(e.target.checked)} /> Preserve columns
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="checkbox" checked={writeNormalizedCopy} onChange={e => setWriteNormalizedCopy(e.target.checked)} /> Write normalized copy
        </label>
        <button disabled={busy} onClick={async () => {
          setNormReport(null)
          const f = inputRef.current?.files?.[0]
          const fd = new FormData()
          if (f) fd.append('file', f)
          if (session) fd.append('session', session)
          const res = await fetch(apiUrl('/excel/normalize_report'), { method: 'POST', body: fd })
          setNormReport(await res.json())
        }}>Show normalization report</button>
        {normalizedCopyPath && (
          <a style={{ marginLeft: 12 }} href={fileHrefFromOutputPath(normalizedCopyPath)} target="_blank" rel="noopener noreferrer" download>
            Download normalized copy
          </a>
        )}
      </div>
      {preview && (
        <div style={{ marginTop: 8 }}>
          <strong>Preview:</strong>
          <pre style={{ maxHeight: 240, overflow: 'auto', background: '#fafafa', padding: 8 }}>
            {JSON.stringify(preview, null, 2)}
          </pre>
        </div>
      )}
      {normReport && (
        <div style={{ marginTop: 8 }}>
          <strong>Normalization Report:</strong>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ minWidth: 260 }}>
              <div style={{ fontWeight: 'bold' }}>Renames</div>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead><tr><th style={{ textAlign: 'left' }}>From</th><th style={{ textAlign: 'left' }}>To</th></tr></thead>
                <tbody>
                  {Object.entries((normReport.report || normReport).proposed_renames || {}).map(([from, to]) => (
                    <tr key={from}><td>{from}</td><td>{String(to)}</td></tr>
                  ))}
                  {Object.keys((normReport.report || normReport).proposed_renames || {}).length === 0 && (
                    <tr><td colSpan={2}><em>None</em></td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div style={{ minWidth: 260 }}>
              <div style={{ fontWeight: 'bold' }}>Missing Columns</div>
              <ul>
                {((normReport.report || normReport).missing_target_columns || []).map((c: string) => (
                  <li key={c}>{c}</li>
                ))}
                {(((normReport.report || normReport).missing_target_columns || []).length === 0) && <li><em>None</em></li>}
              </ul>
            </div>
            <div style={{ minWidth: 260 }}>
              <div style={{ fontWeight: 'bold' }}>Extra Columns</div>
              <ul>
                {((normReport.report || normReport).extra_columns || []).map((c: string) => (
                  <li key={c}>{c}</li>
                ))}
                {(((normReport.report || normReport).extra_columns || []).length === 0) && <li><em>None</em></li>}
              </ul>
            </div>
          </div>
        </div>
      )}
    </Section>
  )
}

function DatastoreViewer() {
  const { session } = useSessionState()
  const [data, setData] = useState<any>(null)
  const [status, setStatus] = useState<string>('')
  const load = async () => {
    if (!session) { setStatus('No session'); return }
    setStatus('Loading…')
    const res = await fetch(apiUrl(`/session/${session}/datastore`))
    const json = await res.json()
    setData(json)
    setStatus('')
  }
  useEffect(() => { if (session) load() }, [session])
  return (
    <Section title="Datastore (Session Backbone)">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button onClick={load}>Refresh</button>
        {session && (
          <a style={{ marginLeft: 8 }} href={apiUrl(`/session/${session}/export_excel`)} target="_blank" rel="noopener noreferrer" download>
            Download canonical Excel
          </a>
        )}
        {status && <small>{status}</small>}
      </div>
      {data && (
        <pre style={{ maxHeight: 260, overflow: 'auto', background: '#fafafa', padding: 8 }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
      {!data && <small>Ready when session is set.</small>}
    </Section>
  )
}

function HudRun({ enabled }: { enabled: boolean }) {
  const { session } = useSessionState()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState<any>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [outputs, setOutputs] = useState<any>(null)
  const [status, setStatus] = useState<string>("")
  const [inputConfig, setInputConfig] = useState<string | null>(null)
  const [updatedExcel, setUpdatedExcel] = useState<string | null>(null)
  const [updatingExcel, setUpdatingExcel] = useState<boolean>(false)

  const submit = async () => {
    const f = inputRef.current?.files?.[0]
    if (!f) return
    setBusy(true); setStatus('Starting HUD run…')
    const fd = new FormData()
    fd.append('file', f)
    if (session) fd.append('session', session)
    try {
      const res = await fetch(apiUrl('/hud/run'), { method: 'POST', body: fd })
      const json = await res.json()
      setJob(json)
      setLogs([])
      setOutputs(null)
      setStatus('Running…')
    } catch (e) {
      setStatus('Failed to start HUD run')
      setBusy(false)
      return
    }

    const ws = new WebSocket(wsUrl(`/ws/jobs/${json.job_id}`))
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'log') setLogs(prev => {
        const next = [...prev, msg.data]
        return next.length > 1000 ? next.slice(-1000) : next
      })
      if (msg.type === 'status' && msg.status === 'completed') {
        fetch(apiUrl(`/jobs/${json.job_id}`)).then(r => r.json()).then(setOutputs)
        setStatus('Completed')
        setBusy(false)
      }
    }
  }

  const runWithValidated = async () => {
    // Use previously validated JSON in session
    setBusy(true); setStatus('Starting HUD run with validated JSON…')
    const fd = new FormData()
    if (session) fd.append('session', session)
    let json: any
    try {
      const res = await fetch(apiUrl('/hud/run'), { method: 'POST', body: fd })
      json = await res.json()
      setJob(json)
      setLogs([])
      setOutputs(null)
      setStatus('Running…')
      if (json.input_config) setInputConfig(json.input_config)
    } catch (e) {
      setStatus('Failed to start HUD run')
      setBusy(false)
      return
    }
    const ws = new WebSocket(wsUrl(`/ws/jobs/${json?.job_id || ''}`))
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'log') setLogs(prev => {
        const next = [...prev, msg.data]
        return next.length > 1000 ? next.slice(-1000) : next
      })
      if (msg.type === 'status' && msg.status === 'completed') {
        fetch(apiUrl(`/jobs/${json?.job_id || ''}`)).then(r => r.json()).then(setOutputs)
        setStatus('Completed')
        setBusy(false)
      }
    }
  }

  return (
    <Section title="HUD Run">
      <input type="file" accept=".json" ref={inputRef} />
      <button disabled={!enabled || busy} onClick={submit} title={!enabled ? 'Upload and verify Excel first' : 'Run HUD'}>{busy ? 'Running…' : 'Run'}</button>
      <button style={{ marginLeft: 8 }} disabled={!enabled || busy} onClick={runWithValidated} title={!enabled ? 'Run is enabled after validation' : 'Run with validated JSON from previous step'}>
        {busy ? 'Running…' : 'Run with validated JSON'}
      </button>
      {status && <small style={{ marginLeft: 8, color: '#555' }}>{status}</small>}
      {inputConfig && (
        <a style={{ marginLeft: 12 }} href={fileHrefFromOutputPath(inputConfig)} target="_blank" rel="noopener noreferrer" download>
          Download actual HUD input
        </a>
      )}
      {job && <div>Job: {job.job_id}</div>}
      <div style={{ display: 'flex', gap: 16 }}>
        <LogViewer lines={logs} />
        <div style={{ flex: 1 }}>
          {outputs && (
            <div>
              <div>Status: {outputs.status}</div>
              {outputs.fast_results && (
                <div><a href={fileHrefFromOutputPath(outputs.fast_results)} target="_blank" rel="noopener noreferrer">fast_results.json</a></div>
              )}
              {outputs.pdf && (
                <div><a href={fileHrefFromOutputPath(outputs.pdf)} target="_blank" rel="noopener noreferrer">HUD_ASD_Results.pdf</a></div>
              )}
              {outputs.status === 'completed' && (
                <div style={{ marginTop: 8 }}>
                  <button disabled={updatingExcel} onClick={async () => {
                    setUpdatingExcel(true); setUpdatedExcel(null)
                    try {
                      const fd = new FormData()
                      // rely on session use in API to pick latest Excel + fast_results
                      const res = await fetch(apiUrl('/excel/update-with-results'), { method: 'POST', body: fd })
                      const json = await res.json()
                      if (json && json.excel) setUpdatedExcel(json.excel)
                    } catch (e) {
                      // ignore for now, could show toast
                    } finally {
                      setUpdatingExcel(false)
                    }
                  }}>{updatingExcel ? 'Updating Excel…' : 'Update Excel file with results from HUD run'}</button>
                  {updatedExcel && (
                    <a style={{ marginLeft: 12 }} href={fileHrefFromOutputPath(updatedExcel)} target="_blank" rel="noopener noreferrer">Download updated Excel</a>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Section>
  )
}

function UpdateExcel() {
  const { session } = useSessionState()
  const excelRef = useRef<HTMLInputElement | null>(null)
  const resultsRef = useRef<HTMLInputElement | null>(null)
  const [out, setOut] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string>("")

  const submit = async () => {
    setBusy(true); setStatus('Updating Excel…')
    const fd = new FormData()
    const ex = excelRef.current?.files?.[0]
    const fr = resultsRef.current?.files?.[0]
    if (ex) fd.append('excel', ex)
    if (fr) fd.append('hud_results', fr)
    if (session) fd.append('session', session)
    try {
      const res = await fetch(apiUrl('/excel/update-with-results'), { method: 'POST', body: fd })
      const json = await res.json()
      setOut(json)
      setStatus('Excel updated')
    } catch (e) {
      setStatus('Failed to update Excel')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="Update Excel with HUD results">
      <div id="update-excel-anchor" />
      <div><input type="file" accept=".xlsx,.xls" ref={excelRef} /> Excel (optional)</div>
      <div><input type="file" accept=".json" ref={resultsRef} /> fast_results.json (optional)</div>
      <button disabled={busy} onClick={submit}>{busy ? 'Updating…' : 'Update'}</button>
      {status && <small style={{ marginLeft: 8, color: '#555' }}>{status}</small>}
      {out?.excel && (
        <div>
          <a href={fileHrefFromOutputPath(out.excel)} target="_blank" rel="noopener noreferrer">Download with_hud.xlsx</a>
          {out.preview && (
            <pre style={{ maxHeight: 240, overflow: 'auto', background: '#fafafa', padding: 8 }}>{JSON.stringify(out.preview, null, 2)}</pre>
          )}
        </div>
      )}
    </Section>
  )
}

function Compliance() {
  const { session } = useSessionState()
  const excelRef = useRef<HTMLInputElement | null>(null)
  const resultsRef = useRef<HTMLInputElement | null>(null)
  const polyRef = useRef<HTMLInputElement | null>(null)
  const [out, setOut] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string>("")

  const submit = async () => {
    setBusy(true); setStatus('Running compliance…')
    const fd = new FormData()
    const ex = excelRef.current?.files?.[0]
    const fr = resultsRef.current?.files?.[0]
    const po = polyRef.current?.files?.[0]
    if (ex) fd.append('excel', ex)
    if (fr) fd.append('hud_results', fr)
    if (po) fd.append('polygon', po)
    if (session) fd.append('session', session)
    try {
      const res = await fetch(apiUrl('/compliance/check'), { method: 'POST', body: fd })
      const json = await res.json()
      setOut(json)
      setStatus('Report ready')
    } catch (e) {
      setStatus('Compliance failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="Compliance Check">
      <div><input type="file" accept=".xlsx,.xls" ref={excelRef} /> Excel (optional)</div>
      <div><input type="file" accept=".json" ref={resultsRef} /> fast_results.json (optional)</div>
      <div><input type="file" accept=".txt" ref={polyRef} /> polygon (optional)</div>
      <button disabled={busy} onClick={submit}>{busy ? 'Checking…' : 'Check'}</button>
      {status && <small style={{ marginLeft: 8, color: '#555' }}>{status}</small>}
      {out?.report && (
        <div><a href={fileHrefFromOutputPath(out.report)} target="_blank" rel="noopener noreferrer">Download compliance report</a></div>
      )}
    </Section>
  )
}

function FilesList() {
  const [files, setFiles] = useState<string[]>([])
  const refresh = async () => {
    const res = await fetch(apiUrl('/files'))
    const json = await res.json()
    setFiles(json.files || [])
  }
  useEffect(() => { refresh() }, [])
  return (
    <Section title="Output Files">
      <button onClick={refresh}>Refresh</button>
      <ul>
        {files.map(f => (
          <li key={f}><a href={apiUrl(`/files/${f}`)} target="_blank" rel="noopener noreferrer">{f}</a></li>
        ))}
      </ul>
    </Section>
  )
}

function App() {
  const [validated, setValidated] = useState(false)
  const onValidated = (ok: boolean) => setValidated(ok)
  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      <h1>HUD Pipeline</h1>
      <KmzParse />
      <ManualExcelStep />
      <ExcelToJson onValidated={onValidated} />
      <HudRun enabled={validated} />
      <UpdateExcel />
      <Compliance />
      <DatastoreViewer />
      <FilesList />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)

// --- Manual step component to explicitly mark KMZ → manual Excel editing separation ---
function ManualExcelStep() {
  const { session } = useSessionState()
  const storageKey = session ? `manualExcelAck:${session}` : 'manualExcelAck'
  const [ack, setAck] = useState<boolean>(false)

  useEffect(() => {
    const v = localStorage.getItem(storageKey)
    setAck(v === '1')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session])

  const toggle = (v: boolean) => {
    setAck(v)
    try { localStorage.setItem(storageKey, v ? '1' : '0') } catch {}
  }

  return (
    <Section title="Manual Step: Prepare Excel">
      <p style={{ marginTop: 0 }}>
        After parsing the KMZ, download the template Excel from the section above, open it, and fill the required
        fields for each site before proceeding.
      </p>
      <ul style={{ marginTop: 8 }}>
        <li><strong>Tank Capacity</strong>: include units (e.g., <code>1000 gal</code>; multiple: <code>12000gal, 10000gal</code>).</li>
        <li><strong>Dike Measurements</strong>: <code>Length 4 ft ; Width 3.5 ft</code> or <code>5 ft x 3.5 ft</code> if applicable.</li>
        <li><strong>Optional</strong>: Tank Measurements (L×W×H), notes, keywords (e.g., <em>pressurized</em>, <em>lpg</em>).</li>
      </ul>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <input type="checkbox" checked={ack} onChange={e => toggle(e.target.checked)} />
        I have updated the Excel template and will upload it below.
      </label>
      {!ack && (
        <div style={{ marginTop: 8 }}>
          <small style={{ color: '#a00' }}>This acknowledgment enables the next step (Excel → JSON).</small>
        </div>
      )}
    </Section>
  )
}

function LogViewer({ lines }: { lines: string[] }) {
  const boxRef = useRef<HTMLPreElement | null>(null)
  useEffect(() => {
    const el = boxRef.current
    if (!el) return
    // Auto-scroll to bottom on update
    el.scrollTop = el.scrollHeight
  }, [lines])
  return (
    <pre ref={boxRef} style={{ flex: 1, maxHeight: 220, overflow: 'auto', background: '#111', color: '#0f0', padding: 8 }}>
      {lines.join('\n')}
    </pre>
  )
}
