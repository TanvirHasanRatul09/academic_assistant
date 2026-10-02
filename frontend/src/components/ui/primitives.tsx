import type { AnchorHTMLAttributes, ButtonHTMLAttributes, HTMLAttributes, ReactElement, ReactNode } from 'react'
import { cloneElement, isValidElement, useId } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; loading?: boolean }

export function Button({ variant = 'primary', size = 'md', loading = false, disabled, className = '', children, ...props }: ButtonProps) {
  return <button className={`ui-button ui-button-${variant} ui-button-${size} ${className}`.trim()} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
    {loading && <Spinner size="sm" label="" />}<span>{loading ? 'Please wait…' : children}</span>
  </button>
}

export function IconButton({ label, icon, size = 'md', ...props }: Omit<ButtonProps, 'children' | 'aria-label'> & { label: string; icon: ReactNode }) {
  return <Button className="ui-icon-button" size={size} aria-label={label} title={label} {...props}>{icon}</Button>
}

export function LinkButton({ variant = 'primary', className = '', children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: ButtonVariant }) {
  return <a className={`ui-button ui-button-${variant} ui-button-md ${className}`.trim()} {...props}>{children}</a>
}

export function Badge({ tone = 'neutral', children, className = '', ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info' }) {
  return <span className={`ui-badge ui-badge-${tone} ${className}`.trim()} {...props}>{children}</span>
}

export function Avatar({ name, src, size = 'md' }: { name: string; src?: string | null; size?: 'sm' | 'md' | 'lg' }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || '?'
  return <span className={`ui-avatar ui-avatar-${size}`} aria-label={name}>{src ? <img src={src} alt="" /> : initials}</span>
}

export function Card({ as: Element = 'article', elevated = false, className = '', ...props }: HTMLAttributes<HTMLElement> & { as?: 'article' | 'section' | 'div'; elevated?: boolean }) {
  return <Element className={`ui-card${elevated ? ' ui-card-elevated' : ''} ${className}`.trim()} {...props} />
}

export function Divider({ label }: { label?: string }) {
  return label ? <div className="ui-divider ui-divider-labelled" role="separator"><span>{label}</span></div> : <hr className="ui-divider" />
}

export function Skeleton({ lines = 1, label = 'Loading content' }: { lines?: number; label?: string }) {
  return <div className="ui-skeleton" role="status" aria-label={label}>{Array.from({ length: lines }, (_, index) => <span key={index} />)}</div>
}

export function Spinner({ size = 'md', label = 'Loading' }: { size?: 'sm' | 'md' | 'lg'; label?: string }) {
  return <span className={`ui-spinner ui-spinner-${size}`} role={label ? 'status' : undefined} aria-label={label || undefined} aria-hidden={label ? undefined : true} />
}

export function Tooltip({ content, children }: { content: string; children: ReactNode }) {
  const id = useId()
  const trigger = isValidElement(children) ? cloneElement(children as ReactElement<{ 'aria-describedby'?: string }>, { 'aria-describedby': id }) : <span aria-describedby={id}>{children}</span>
  return <span className="ui-tooltip">{trigger}<span className="ui-tooltip-content" id={id} role="tooltip">{content}</span></span>
}
