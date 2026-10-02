import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { useId } from 'react'

export function Field({ label, hint, error, required, children }: { label: string; hint?: string; error?: string; required?: boolean; children: (ids: { id: string; describedBy?: string }) => ReactNode }) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined
  return <div className={`ui-field${error ? ' ui-field-invalid' : ''}`}>
    <label htmlFor={id}>{label}{required && <span aria-hidden="true"> *</span>}</label>
    {children({ id, describedBy })}
    {hint && <p className="ui-field-hint" id={hintId}>{hint}</p>}
    {error && <p className="ui-field-error" id={errorId} role="alert">{error}</p>}
  </div>
}

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`ui-input ${className}`.trim()} {...props} />
}

export function Textarea({ className = '', ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`ui-input ui-textarea ${className}`.trim()} {...props} />
}

export function Select({ className = '', children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`ui-input ui-select ${className}`.trim()} {...props}>{children}</select>
}

export function Checkbox({ label, description, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { label: string; description?: string }) {
  const id = useId()
  const descriptionId = description ? `${id}-description` : undefined
  return <label className="ui-choice" htmlFor={id}>
    <input id={id} type="checkbox" aria-describedby={descriptionId} {...props} />
    <span><strong>{label}</strong>{description && <small id={descriptionId}>{description}</small>}</span>
  </label>
}

export function Radio({ label, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { label: string }) {
  const id = useId()
  return <label className="ui-choice" htmlFor={id}><input id={id} type="radio" {...props} /><span>{label}</span></label>
}

export function Switch({ label, description, checked, onChange, disabled, name }: { label: string; description?: string; checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean; name?: string }) {
  const id = useId()
  return <label className="ui-switch-row" htmlFor={id}>
    <span><strong>{label}</strong>{description && <small>{description}</small>}</span>
    <input id={id} className="ui-switch-input" name={name} type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
    <span className="ui-switch-track" aria-hidden="true"><span /></span>
  </label>
}

export function DateControl(props: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>) {
  return <Input type="date" {...props} />
}

export function ValidationMessage({ children }: { children: ReactNode }) {
  return <p className="ui-field-error" role="alert">{children}</p>
}
