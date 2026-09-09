import { useEffect, useRef } from 'react'
import {
  ArrowLeft, ArrowRight, Bookmark, CalendarDays, ChevronDown, ChevronLeft, ChevronRight,
  Film, Grid2X2, Heart, Leaf, Map, Menu, MoreHorizontal, Pin, Plus, Search, Settings2,
  Sparkles, Star, Sun, Tag, History as TimelineIcon, Users, X,
} from 'lucide-react'
import { formatMemoryDate, launcherChoices, memoryTypeLabels, navItems } from '../../data/tandemData'

const iconMap = { sun: Sun, timeline: TimelineIcon, search: Search, calendar: CalendarDays }
const launcherIconMap = { film: Film, pin: Pin, map: Map, sparkles: Sparkles, plus: Plus }

export function Sidebar({ path, onNavigate, onAddMemory }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true"><span>t</span></div>
        <div><div className="brand-name">tandem</div><div className="brand-caption">shared memories</div></div>
      </div>
      <button className="add-memory-button" onClick={onAddMemory}><Plus size={17} strokeWidth={2.5} /><span>Add memory</span><span className="shortcut">N</span></button>
      <nav className="primary-nav">
        <div className="nav-section-label">Your space</div>
        {navItems.map((item) => {
          const Icon = iconMap[item.icon]
          const active = item.path === '/' ? path === '/' : path.startsWith(item.path)
          return <a href={item.path} key={item.path} className={`nav-item ${active ? 'active' : ''}`} aria-current={active ? 'page' : undefined} onClick={(event) => { event.preventDefault(); onNavigate(item.path) }}><Icon size={18} /><span>{item.label}</span>{item.label === 'Today' && <span className="nav-live-dot" />}</a>
        })}
      </nav>
      <div className="sidebar-lower">
        <div className="nav-section-label">Your tandem</div>
        <button className="tandem-mini-switcher" onClick={() => onNavigate('/tandem')}><span className="mini-avatar avatar-berry">R</span><span className="mini-avatar avatar-clay">A</span><span className="tandem-mini-name">Raj &amp; Alex</span><ChevronDown size={15} /></button>
        <a href="/tandem" className="nav-item" onClick={(event) => { event.preventDefault(); onNavigate('/tandem') }}><Users size={18} /><span>Our tandem</span></a>
        <div className="sidebar-rule" />
        <button className="sidebar-settings"><Settings2 size={17} /><span>Settings</span></button>
      </div>
      <div className="sidebar-footer"><span className="private-dot" />Private space <span className="footer-spacer" />v1.0</div>
    </aside>
  )
}

export function TopBar({ path, onNavigate, query, onQueryChange }) {
  const title = path === '/' ? 'Today' : path.slice(1).split('/')[0].replace(/-/g, ' ')
  return <header className="topbar">
    <div className="topbar-context"><span className="context-kicker">Raj &amp; Alex</span><span className="context-slash">/</span><span className="context-page">{title}</span></div>
    <div className="topbar-actions">
      <label className="top-search"><Search size={16} /><span className="sr-only">Search memories</span><input value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') onNavigate(`/explore${query ? `?q=${encodeURIComponent(query)}` : ''}`) }} placeholder="Search memories" /><span className="search-key">⌘ K</span></label>
      <button className="top-tandem-switcher" onClick={() => onNavigate('/tandem')}><span className="mini-avatar avatar-berry">R</span><span className="mini-avatar avatar-clay">A</span><span>Raj &amp; Alex</span><ChevronDown size={15} /></button>
      <button className="top-avatar" aria-label="Open account settings" onClick={() => onNavigate('/tandem')}>RR</button>
    </div>
  </header>
}

export function AppShell({ children, path, onNavigate, onAddMemory, query, onQueryChange }) {
  return <div className="app-frame"><Sidebar path={path} onNavigate={onNavigate} onAddMemory={onAddMemory} /><div className="app-main"><TopBar path={path} onNavigate={onNavigate} query={query} onQueryChange={onQueryChange} /><main className="main-canvas">{children}</main></div></div>
}

export function PageHeader({ eyebrow, title, description, action, children }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action || children}</div>
}

export function SectionHeader({ eyebrow, title, action, onAction }) {
  return <div className="section-header"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2></div>{action && <button className="text-action" onClick={onAction}>{action}<ArrowRight size={15} /></button>}</div>
}

export function AvatarStack({ members, size = 'normal' }) {
  return <div className={`avatar-stack avatar-stack-${size}`} aria-label={`${members.map((member) => member.name).join(' and ')}`}>
    {members.map((member) => <span className="avatar" key={member.id} style={{ backgroundColor: member.color }} title={member.name}>{member.initials}</span>)}
  </div>
}

export function FilterChip({ active = false, children, onClick, icon }) {
  return <button className={`filter-chip ${active ? 'active' : ''}`} aria-pressed={active} onClick={onClick}>{icon}{children}</button>
}

export function MemoryBadge({ type }) {
  return <span className={`memory-badge badge-${type}`}>{memoryTypeLabels[type]}</span>
}

export function MemoryCard({ memory, variant = 'standard', onOpen }) {
  return <article className={`memory-card memory-card-${variant}`}>
    <button className="memory-card-media" onClick={() => onOpen(memory.id)} aria-label={`Open memory: ${memory.title}`}><img src={memory.image} alt={memory.imageAlt} loading="lazy" /><span className="memory-card-fade" /><span className="memory-card-type"><MemoryBadge type={memory.type} /></span><span className="open-circle"><ArrowRight size={15} /></span></button>
    <div className="memory-card-body"><div className="memory-card-meta"><span>{formatMemoryDate(memory.date, 'short')}</span>{memory.location && <><span className="meta-separator">·</span><span>{memory.location}</span></>}</div><button className="memory-card-title" onClick={() => onOpen(memory.id)}>{memory.title}</button><p>{memory.excerpt}</p><div className="memory-card-footer"><AvatarStack members={memory.participants.map((name, index) => ({ id: name, name, initials: name[0], color: index === 0 ? '#8f4357' : '#b86d57' }))} size="small" />{memory.rating && <span className="rating"><Star size={12} fill="currentColor" /> {memory.rating}/10</span>}<button className="card-more" aria-label={`More options for ${memory.title}`}><MoreHorizontal size={17} /></button></div></div>
  </article>
}

export function PhotoStack({ memories, onOpen }) {
  return <div className="photo-stack" aria-label="A stack of shared memories">
    {memories.slice(0, 3).map((memory, index) => <button key={memory.id} className={`stack-photo stack-photo-${index + 1}`} onClick={() => onOpen(memory.id)} aria-label={`Open ${memory.title}`}><img src={memory.image} alt="" /></button>)}
    <span className="stack-caption">and 144 more</span>
  </div>
}

export function EmptyState({ title, description, action, onAction }) {
  return <div className="empty-state"><div className="empty-state-icon"><Leaf size={21} /></div><h3>{title}</h3><p>{description}</p>{action && <button className="button button-secondary" onClick={onAction}>{action}<ArrowRight size={15} /></button>}</div>
}

export function SkeletonCard() {
  return <div className="skeleton-card" aria-label="Loading memory"><div className="skeleton skeleton-media" /><div className="skeleton skeleton-line wide" /><div className="skeleton skeleton-line" /><div className="skeleton skeleton-line short" /></div>
}

export function AnniversaryHero({ memory, copy, onOpen, onAddMemory }) {
  return <section className={`anniversary-hero ${copy.fallback ? 'anniversary-hero-fallback' : ''}`}>
    <div className="hero-image-wrap">{memory ? <img src={memory.image} alt={memory.imageAlt} /> : <div className="hero-fallback-pattern"><span>✦</span><span>✧</span><span>·</span></div>}<div className="hero-image-overlay" /><div className="hero-date-stamp"><span className="stamp-day">09</span><span className="stamp-month">SEP<br />2026</span></div></div>
    <div className="hero-copy"><div className="hero-copy-top"><span className="eyebrow hero-eyebrow">{copy.eyebrow}</span><span className="hero-sparkle">✦</span></div><h2>{copy.title}</h2><p className="hero-excerpt">{copy.excerpt}</p>{memory && <div className="hero-meta"><span><Pin size={14} /> {memory.location}</span><span><Users size={14} /> With {memory.participants.join(' & ')}</span></div>}<div className="hero-actions">{memory ? <button className="button button-light" onClick={() => onOpen(memory.id)}>Open memory <ArrowRight size={15} /></button> : <button className="button button-light" onClick={onAddMemory}>Add a memory <Plus size={15} /></button>}<button className="hero-save" aria-label="Save this memory"><Bookmark size={17} /></button></div></div>
  </section>
}

export function AddMemoryLauncher({ open, onClose, onChoose }) {
  const firstChoice = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const handleKeyDown = (event) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKeyDown)
    firstChoice.current?.focus()
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])
  if (!open) return null
  return <div className="launcher-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="launcher-dialog" role="dialog" aria-modal="true" aria-labelledby="launcher-title"><div className="launcher-heading"><div><div className="eyebrow">Make a little room for it</div><h2 id="launcher-title">What are we remembering?</h2><p>Start with the shape of the memory. You can fill in the details as you go.</p></div><button className="icon-button" onClick={onClose} aria-label="Close add memory dialog"><X size={19} /></button></div><div className="launcher-grid">{launcherChoices.map((choice, index) => { const Icon = launcherIconMap[choice.icon]; return <button key={choice.type} ref={index === 0 ? firstChoice : undefined} className="launcher-choice" onClick={() => onChoose(choice.type)}><span className={`launcher-choice-icon launcher-${choice.type}`}><Icon size={20} /></span><span><strong>{choice.label}</strong><small>{choice.note}</small></span><ArrowRight size={16} className="launcher-arrow" /></button> })}</div><div className="launcher-footer"><span className="private-dot" />Only people in your tandem can see what you add.</div></section></div>
}

export function MemoryDetail({ memory, onBack, onAddMemory }) {
  return <div className="detail-page"><button className="back-link" onClick={onBack}><ArrowLeft size={15} /> Back to {memory.type === 'movie' ? 'explore' : 'timeline'}</button><div className="detail-layout"><div className="detail-media"><img src={memory.image} alt={memory.imageAlt} /><span className="detail-media-label">{memoryTypeLabels[memory.type]} · {new Date(memory.date).getFullYear()}</span></div><article className="detail-copy"><div className="eyebrow">{formatMemoryDate(memory.date)}</div><div className="detail-heading-row"><h1>{memory.title}</h1><button className="icon-button" aria-label="More memory options"><MoreHorizontal size={20} /></button></div><div className="detail-location"><Pin size={16} /> {memory.location}</div><p className="detail-excerpt">{memory.excerpt}</p>{memory.notes && <blockquote>{memory.notes}</blockquote>}<div className="detail-divider" /><div className="detail-meta-grid"><div><span>With</span><strong>{memory.participants.join(' & ')}</strong></div>{memory.rating && <div><span>Rating</span><strong className="detail-rating"><Star size={15} fill="currentColor" /> {memory.rating}/10</strong></div>}<div><span>Added</span><strong>By Raj</strong></div></div><div className="tag-row">{memory.tags.map((tag) => <span className="tag" key={tag}><Tag size={12} />{tag}</span>)}</div><button className="button button-primary detail-add" onClick={onAddMemory}><Plus size={16} /> Add another memory</button></article></div></div>
}

export function MonthSwitcher({ label, onPrevious, onNext }) {
  return <div className="month-switcher"><button onClick={onPrevious} aria-label="Previous month"><ChevronLeft size={17} /></button><strong>{label}</strong><button onClick={onNext} aria-label="Next month"><ChevronRight size={17} /></button></div>
}

export function SearchField({ value, onChange, placeholder = 'Search your memories' }) {
  return <label className="explore-search"><Search size={18} /><span className="sr-only">{placeholder}</span><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>
}

export function TypeIcon({ type }) {
  const Icon = type === 'movie' ? Film : type === 'place' ? Pin : type === 'trip' ? Map : type === 'moment' ? Heart : Sparkles
  return <Icon size={15} />
}

export function CalendarCell({ day, memory, selected, onSelect }) {
  return <button className={`calendar-cell ${selected ? 'selected' : ''} ${memory ? 'has-memory' : ''}`} onClick={onSelect} aria-label={memory ? `${day} September, ${memory.title}` : `${day} September, no memories`}><span className="calendar-day-number">{day}</span>{memory ? <><img src={memory.image} alt="" /><span className="calendar-cell-title">{memory.title}</span></> : <span className="calendar-cell-empty" />}</button>
}

export function CalendarPanel({ memory, onOpen }) {
  if (!memory) return <div className="calendar-side-empty"><CalendarDays size={26} /><p>Select a date to revisit what happened.</p></div>
  return <div className="calendar-side-panel"><div className="eyebrow">{formatMemoryDate(memory.date)}</div><h3>{memory.title}</h3><div className="side-panel-place"><Pin size={14} /> {memory.location}</div><img src={memory.image} alt={memory.imageAlt} /><p>{memory.excerpt}</p><button className="text-action" onClick={() => onOpen(memory.id)}>Open memory <ArrowRight size={15} /></button></div>
}
