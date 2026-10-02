import { useEffect, useState } from 'react'
import { getRelevanceDebug, type RelevanceDebugItem } from '../api'

export function RelevanceDebugPage() {
  const [items, setItems] = useState<RelevanceDebugItem[]>([])
  const [error, setError] = useState('')
  useEffect(() => { getRelevanceDebug().then(setItems).catch((caught) => setError(caught instanceof Error ? caught.message : 'Could not load relevance decisions.')) }, [])
  return <section className="settings-layout" aria-labelledby="relevance-debug-title"><div className="form-card"><p className="eyebrow">Development diagnostics</p><h1 id="relevance-debug-title">Relevance debug</h1><p>Only your selected-course records are shown. This route is unavailable in production.</p>{error && <p role="alert">{error}</p>}<div className="debug-list">{items.map((item) => <article className="form-card" key={item.event_id}><p className="course-name">{item.course}</p><h2>{item.title}</h2><p><strong>{item.relevant ? 'Relevant' : item.review_required ? 'Uncertain' : 'Excluded'}:</strong> {item.reason}</p><pre>{JSON.stringify(item.targeting, null, 2)}</pre></article>)}</div></div></section>
}
