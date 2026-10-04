import { ArrowLeft, Bot, Database, Link2, LogOut, ShieldCheck, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Logo from '../components/Logo'

export default function SettingsPage() {
  const navigate = useNavigate()
  const [account, setAccount] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api('/api/account').then(setAccount).catch(() => navigate('/login')) }, [navigate])

  async function signOut() {
    await api('/api/logout', { method: 'POST' })
    navigate('/login')
  }

  async function disconnect() {
    if (!window.confirm('Disconnect this mailbox and delete its stored OAuth tokens?')) return
    try { await api('/api/account', { method: 'DELETE' }); navigate('/login') } catch (event) { setError(event.message) }
  }

  if (!account) return <div className="loading"><span /><p>Loading account settings…</p></div>
  const connection = account.connection

  return <main className="settings-page"><header><Logo dark /><button onClick={() => navigate('/dashboard')}><ArrowLeft size={17} />Back to dashboard</button></header><section className="settings-heading"><p className="kicker">WORKSPACE CONTROL</p><h1>Settings</h1><p>Manage your connected mailbox, AI provider and account security.</p></section>{error && <div className="auth-error">{error}</div>}<section className="settings-grid"><article className="settings-card"><span className="settings-icon"><Link2 /></span><div><h2>Mailbox connection</h2><p>Your provider authorization is encrypted and retained when you sign out.</p><dl><div><dt>Status</dt><dd className="connected">● {connection ? 'Connected' : 'Demo mode'}</dd></div><div><dt>Provider</dt><dd>{connection?.provider || account.user.provider}</dd></div><div><dt>Email</dt><dd>{account.user.email}</dd></div><div><dt>Updated</dt><dd>{connection?.updated_at ? new Date(connection.updated_at).toLocaleString() : 'Not applicable'}</dd></div></dl></div></article><article className="settings-card"><span className="settings-icon purple"><Bot /></span><div><h2>AI intelligence</h2><p>The active provider controls semantic classification and summaries.</p><dl><div><dt>Provider</dt><dd>{account.ai.provider}</dd></div><div><dt>Groq model</dt><dd>{account.ai.groq_model}</dd></div><div><dt>Private model</dt><dd>{account.ai.ollama_model}</dd></div><div><dt>Fallback</dt><dd>Deterministic rules</dd></div></dl></div></article><article className="settings-card"><span className="settings-icon green"><ShieldCheck /></span><div><h2>Security and retention</h2><p>Tokens remain on the backend and are never exposed to the React application.</p><ul><li><Database />Encrypted token storage</li><li><ShieldCheck />Read-only mailbox permissions</li><li><ShieldCheck />Seven-day remembered session</li></ul></div></article></section><section className="account-actions"><div><h2>Session</h2><p>Signing out clears this browser session but keeps the mailbox connection. Google may ask you to identify yourself again, but it should not repeat consent.</p><button className="secondary-action" onClick={signOut}><LogOut size={16} />Sign out</button></div><div className="danger-zone"><h2>Disconnect mailbox</h2><p>This permanently removes the saved OAuth tokens and account connection from InboxPilot.</p><button onClick={disconnect} disabled={!connection}><Trash2 size={16} />Disconnect and delete tokens</button></div></section></main>
}
