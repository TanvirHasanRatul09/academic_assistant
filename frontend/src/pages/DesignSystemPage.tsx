import { useState } from 'react'
import {
  Avatar, Badge, Button, Card, Checkbox, CommandSearch, DateControl, Divider, EmptyState,
  Field, FilterBar, IconButton, Input, PageHeader, PartialDataState, Radio, ResponsiveDataList,
  SectionHeader, Select, Skeleton, Spinner, StatCard, Switch, Tabs, Textarea, Tooltip,
} from '../components/ui'

const colors = [
  ['Canvas', 'var(--color-canvas)'], ['Raised canvas', 'var(--color-canvas-raised)'],
  ['Surface', 'var(--color-surface)'], ['Raised surface', 'var(--color-surface-raised)'],
  ['Accent', 'var(--color-accent)'], ['Highlight', 'var(--color-highlight)'],
  ['Success', 'var(--color-success)'], ['Warning', 'var(--color-warning)'], ['Danger', 'var(--color-danger)'],
]

export function DesignSystemPage() {
  const [enabled, setEnabled] = useState(true)
  const [tab, setTab] = useState('components')
  const [search, setSearch] = useState('')
  const sampleItems = [{ id: '1', title: 'Research outline', meta: 'Due tomorrow' }, { id: '2', title: 'Physics review', meta: 'Exam · Friday' }]

  return <section className="design-gallery" aria-labelledby="design-gallery-title">
    <PageHeader eyebrow="Development only" title="Component library" description="Accessible, typed primitives and product patterns built on the visual foundation." actions={<Button>Primary action</Button>} />

    <section aria-labelledby="gallery-colors"><SectionHeader title="Semantic colors" /><div className="gallery-swatches">{colors.map(([label, color]) => <article className="gallery-swatch" key={label}><span style={{ background: color }} aria-hidden="true" /><strong>{label}</strong></article>)}</div></section>

    <Card elevated><SectionHeader title="Actions and identity" description="Variants share predictable sizing, focus, loading, and disabled behavior." /><div className="gallery-actions"><Button>Primary</Button><Button variant="secondary">Secondary</Button><Button variant="ghost">Ghost</Button><Button variant="danger">Danger</Button><Button loading>Save</Button><IconButton label="Add item" icon="+" /><Tooltip content="Current learner"><Avatar name="Ratul Hasan" /></Tooltip></div><Divider label="Status" /><div className="gallery-actions"><Badge tone="accent">In progress</Badge><Badge tone="success">Synced</Badge><Badge tone="warning">Due soon</Badge><Badge tone="danger">Failed</Badge><Spinner label="Refreshing" /></div></Card>

    <Card><SectionHeader title="Form controls" description="Labels, descriptions, validation, and touch targets are built in." /><div className="gallery-fields">
      <Field label="Search term" hint="Try a course or assignment" required>{({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} defaultValue="Academic work" required />}</Field>
      <Field label="Event type">{({ id, describedBy }) => <Select id={id} aria-describedby={describedBy} defaultValue="assignment"><option value="assignment">Assignment</option><option value="exam">Exam</option></Select>}</Field>
      <Field label="Due date">{({ id, describedBy }) => <DateControl id={id} aria-describedby={describedBy} />}</Field>
      <Field label="Notes" error="Keep this under 200 characters">{({ id, describedBy }) => <Textarea id={id} aria-describedby={describedBy} aria-invalid="true" defaultValue="Plan the next study block." />}</Field>
    </div><div className="gallery-fields"><Checkbox label="Include completed work" description="Useful when reviewing a full course." defaultChecked /><div><Radio name="density" label="Comfortable density" defaultChecked /><Radio name="density" label="Compact density" /></div><Switch label="Deadline reminders" description="Notify before work is due." checked={enabled} onChange={setEnabled} /></div></Card>

    <Card><Tabs label="Component examples" value={tab} onValueChange={setTab} tabs={[{ id: 'components', label: 'Components', panel: <Skeleton lines={3} label="Example loading state" /> }, { id: 'patterns', label: 'Patterns', panel: <PartialDataState title="Some data is still arriving" description="Available coursework remains usable while synchronization finishes." /> }]} /></Card>

    <section><SectionHeader title="Product patterns" description="Responsive headers, filters, statistics, lists, and empty states." /><div className="gallery-geometry"><StatCard label="Upcoming" value="12" detail="Next seven days" tone="accent" /><StatCard label="Completed" value="86%" detail="This semester" tone="success" /><StatCard label="Needs attention" value="3" detail="Due within 24 hours" tone="warning" /></div></section>
    <FilterBar activeCount={1} actions={<Button variant="ghost">Clear</Button>}><CommandSearch value={search} onChange={setSearch} /><Field label="Course">{({ id }) => <Select id={id}><option>All courses</option></Select>}</Field></FilterBar>
    <ResponsiveDataList items={sampleItems} keyOf={(item) => item.id} renderItem={(item) => <><strong>{item.title}</strong><p className="muted-copy">{item.meta}</p></>} />
    <EmptyState title="Nothing needs attention" description="New work and notices will appear here after synchronization." actionLabel="Refresh" onAction={() => undefined} />
  </section>
}
