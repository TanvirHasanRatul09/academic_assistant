import type { KeyboardEvent, ReactNode } from 'react'
import { useEffect, useId, useRef } from 'react'

export function Dialog({ open, onOpenChange, title, description, children, footer, className = '' }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description?: string; children: ReactNode; footer?: ReactNode; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [open])
  return <dialog ref={ref} className={`ui-dialog ${className}`.trim()} aria-labelledby={titleId} aria-describedby={description ? descriptionId : undefined} onCancel={(event) => { event.preventDefault(); onOpenChange(false) }} onClose={() => onOpenChange(false)}>
    <div className="ui-dialog-header"><div><h2 id={titleId}>{title}</h2>{description && <p id={descriptionId}>{description}</p>}</div><button className="ui-dialog-close" type="button" aria-label="Close dialog" onClick={() => onOpenChange(false)}>×</button></div>
    <div className="ui-dialog-body">{children}</div>
    {footer && <footer className="ui-dialog-footer">{footer}</footer>}
  </dialog>
}

export function AlertDialog(props: Parameters<typeof Dialog>[0]) {
  return <Dialog {...props} className={`ui-alert-dialog ${props.className ?? ''}`.trim()} />
}

export function Drawer(props: Parameters<typeof Dialog>[0] & { side?: 'left' | 'right' | 'bottom' }) {
  return <Dialog {...props} className={`ui-drawer ui-drawer-${props.side ?? 'right'} ${props.className ?? ''}`.trim()} />
}

export function Dropdown({ label, children }: { label: ReactNode; children: ReactNode }) {
  return <details className="ui-dropdown"><summary>{label}</summary><div className="ui-floating-panel" role="menu">{children}</div></details>
}

export function Popover({ label, children }: { label: ReactNode; children: ReactNode }) {
  return <details className="ui-popover"><summary>{label}</summary><div className="ui-floating-panel">{children}</div></details>
}

type Tab = { id: string; label: string; panel: ReactNode }
export function Tabs({ tabs, value, onValueChange, label }: { tabs: Tab[]; value: string; onValueChange: (value: string) => void; label: string }) {
  const prefix = useId()
  function keyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    let next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : index + (event.key === 'ArrowRight' ? 1 : -1)
    next = (next + tabs.length) % tabs.length
    onValueChange(tabs[next]!.id)
    const container = event.currentTarget.parentElement
    window.requestAnimationFrame(() => (container?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next])?.focus())
  }
  const selected = tabs.find((tab) => tab.id === value) ?? tabs[0]
  if (!selected) return null
  return <div className="ui-tabs"><div className="ui-tab-list" role="tablist" aria-label={label}>{tabs.map((tab, index) => <button key={tab.id} id={`${prefix}-tab-${tab.id}`} role="tab" aria-selected={tab.id === selected.id} aria-controls={`${prefix}-panel-${tab.id}`} tabIndex={tab.id === selected.id ? 0 : -1} type="button" onClick={() => onValueChange(tab.id)} onKeyDown={(event) => keyDown(event, index)}>{tab.label}</button>)}</div><div id={`${prefix}-panel-${selected.id}`} role="tabpanel" aria-labelledby={`${prefix}-tab-${selected.id}`} tabIndex={0}>{selected.panel}</div></div>
}

export type ToastMessage = { id: string; tone?: 'info' | 'success' | 'warning' | 'danger'; title: string; description?: string }
export function ToastRegion({ messages, onDismiss }: { messages: ToastMessage[]; onDismiss?: (id: string) => void }) {
  return <div className="ui-toast-region" role="region" aria-live="polite" aria-label="Notifications">{messages.map((message) => <article className={`ui-toast ui-toast-${message.tone ?? 'info'}`} key={message.id}><div><strong>{message.title}</strong>{message.description && <p>{message.description}</p>}</div>{onDismiss && <button type="button" aria-label={`Dismiss ${message.title}`} onClick={() => onDismiss(message.id)}>×</button>}</article>)}</div>
}

export function CommandSearch({ label = 'Search', value, onChange, placeholder = 'Search…' }: { label?: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return <div className="ui-command"><label><span>{label}</span><input type="search" value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /></label></div>
}



