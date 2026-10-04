import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, BarChart3, Clock3, Download, Inbox, LogOut, Search, Settings, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Logo from '../components/Logo'

const categories = ['All', 'Important', 'Recruitment', 'Finance', 'Newsletter', 'Spam']
const colors = { Important: '#657be9', Recruitment: '#946ce7', Finance: '#28a67a', Newsletter: '#e6a23c', Spam: '#e26363' }

export default function Dashboard() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [payload, setPayload] = useState({ messages: [], ai: {}, stats: { total: 0, urgent: 0, minutes_saved: 0, categories: {} } })
  const [category, setCategory] = useState('All')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api('/api/me'), api('/api/emails')])
      .then(([profile, emails]) => { setUser(profile); setPayload(emails) })
      .catch(() => navigate('/login'))
      .finally(() => setLoading(false))
  }, [navigate])

  const messages = useMemo(() => payload.messages.filter(message => {
    const text = `${message.sender} ${message.subject} ${message.summary} ${message.action || ''}`.toLowerCase()
    return (category === 'All' || message.category === category) && text.includes(search.toLowerCase())
  }), [payload.messages, category, search])

  const priorities = useMemo(() => payload.messages.reduce((out, message) => {
    out[message.priority] = (out[message.priority] || 0) + 1
    return out
  }, {}), [payload.messages])

  async function logout() {
    await api('/api/logout', { method: 'POST' })
    navigate('/login')
  }

  function exportCsv() {
    const rows = [['Sender', 'Subject', 'Category', 'Priority', 'Sentiment', 'Summary', 'Next action', 'Confidence'], ...messages.map(m => [m.sender, m.subject, m.category, m.priority, m.sentiment, m.summary, m.action || '', m.confidence || ''])]
    const csv = rows.map(row => row.map(value => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\n')
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    link.download = 'inboxpilot-ai-digest.csv'
    link.click()
    URL.revokeObjectURL(link.href)
  }

  if (loading) return <div className="loading"><span /><p>AI is understanding your inbox…</p></div>

  return (
    <div className="app-shell">
      <Sidebar user={user} category={category} setCategory={setCategory} stats={payload.stats} navigate={navigate} logout={logout} />
      <main className="dashboard">
        <div className="ambient ambient-one" /><div className="ambient ambient-two" />
        <header className="dash-header">
          <div><p className="kicker">LIVE EMAIL INTELLIGENCE</p><h1>Good morning, {user?.name?.split(' ')[0]}.</h1><p>Your inbox is classified, summarized and converted into next actions.</p></div>
          <button className="export" onClick={exportCsv}><Download size={17} />Export report</button>
        </header>
        <section className="metrics">
          <Metric icon={<BarChart3 />} label="AI ANALYZED" value={payload.stats.total} hint="Messages today" color="blue" />
          <Metric icon={<AlertTriangle />} label="NEEDS ATTENTION" value={payload.stats.urgent} hint="High priority" color="orange" />
          <Metric icon={<Clock3 />} label="TIME SAVED" value={`${payload.stats.minutes_saved}m`} hint="Estimated today" color="green" />
        </section>
        <section className="intelligence-grid">
          <article className="insight">
            <span><Sparkles /></span>
            <div><b>AI briefing</b><p>{payload.stats.urgent ? `${payload.stats.urgent} messages require prompt action.` : 'No urgent messages detected.'} Results are generated from current inbox content.</p></div>
            <i className={payload.ai.fallback ? 'model-chip fallback' : 'model-chip'}>{payload.ai.provider || 'unknown'} · {payload.ai.model || 'unavailable'}</i>
          </article>
          <article className="distribution-card">
            <div><b>Category distribution</b><small>Live from analyzed messages</small></div>
            <div className="bars">{categories.slice(1).map(item => <Bar key={item} label={item} value={payload.stats.categories[item] || 0} total={payload.stats.total} color={colors[item]} />)}</div>
          </article>
          <article className="priority-card">
            <div><b>Priority mix</b><small>AI-ranked urgency</small></div>
            <div className="priority-ring" style={{ '--high': `${(priorities.High || 0) / Math.max(payload.stats.total, 1) * 360}deg`, '--medium': `${((priorities.High || 0) + (priorities.Medium || 0)) / Math.max(payload.stats.total, 1) * 360}deg` }}><span><b>{payload.stats.total}</b><small>Total</small></span></div>
            <div className="ring-legend"><span className="high-dot">High {priorities.High || 0}</span><span className="medium-dot">Medium {priorities.Medium || 0}</span><span className="low-dot">Low {priorities.Low || 0}</span></div>
          </article>
        </section>
        <section className="mail-section">
          <div className="mail-toolbar"><div><h2>{category} messages</h2><span>{messages.length} results</span></div><label><Search size={17} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search summaries and next actions…" /></label></div>
          <div className="mail-list"><AnimatePresence mode="popLayout">{messages.map((message, index) => <EmailCard key={message.id} message={message} index={index} />)}</AnimatePresence>{!messages.length && <div className="empty"><Inbox /><b>No matching messages</b><p>Try another category or search phrase.</p></div>}</div>
        </section>
      </main>
    </div>
  )
}

function Sidebar({ user, category, setCategory, stats, navigate, logout }) {
  return <aside className="sidebar"><Logo /><p className="nav-label">WORKSPACE</p><nav>{categories.map(item => <button key={item} className={category === item ? 'active' : ''} onClick={() => setCategory(item)}><Inbox size={17} /><span>{item}</span><b>{item === 'All' ? stats.total : stats.categories[item] || 0}</b></button>)}</nav><div className="side-bottom"><button onClick={() => navigate('/settings')}><Settings size={17} /><span>Settings</span></button><div className="profile"><span className="profile-avatar">{user?.name?.[0]}</span><div><b>{user?.name}</b><small>{user?.provider} workspace</small></div><button onClick={logout} title="Sign out"><LogOut size={16} /></button></div></div></aside>
}

function Metric({ icon, label, value, hint, color }) {
  return <motion.article className={`metric ${color}`} whileHover={{ y: -4, rotateX: 2, rotateY: -2 }}><div className="metric-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{hint}</small></div></motion.article>
}

function Bar({ label, value, total, color }) {
  return <div className="bar-row"><span>{label}</span><div><i style={{ width: `${value / Math.max(total, 1) * 100}%`, background: color }} /></div><b>{value}</b></div>
}

function EmailCard({ message, index }) {
  return <motion.article className="email-card" layout initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ delay: Math.min(index * .035, .25) }}><span className="sender-avatar">{message.sender[0]}</span><div className="email-content"><div className="email-title"><h3>{message.subject}</h3><time>{message.received_at}</time></div><p className="sender">{message.sender}</p><p className="summary">{message.summary}</p>{message.action && <p className="next-action"><b>Next action</b>{message.action}</p>}<div className="tags"><span className="tag category">{message.category}</span><span className={`tag ${message.priority.toLowerCase()}`}>{message.priority} priority</span><span className="tag">{message.sentiment}</span>{message.confidence != null && <span className="tag confidence">{Math.round(message.confidence * 100)}% confidence</span>}</div></div></motion.article>
}
