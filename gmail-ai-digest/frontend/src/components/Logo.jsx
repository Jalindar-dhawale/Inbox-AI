import {Sparkles} from 'lucide-react'
export default function Logo({dark=false}){return <div className={`logo ${dark?'logo-dark':''}`}><span className="logo-mark"><Sparkles size={18}/></span><span><b>InboxPilot</b><small>AI EMAIL INTELLIGENCE</small></span></div>}
