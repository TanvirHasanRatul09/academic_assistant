import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardItem } from '../api'
import { DashboardTaskCard } from './DashboardTaskCard'

function item(overrides: Partial<DashboardItem> = {}): DashboardItem {
  return { task_id: 't1', event_id: 'e1', course_id: 'c1', course_name: 'Physics', title: 'Lab report', body: 'Prepare the final analysis.', source_type: 'coursework', source_url: 'https://classroom.google.com/example', source_created_at: '2026-09-20T00:00:00Z', source_updated_at: new Date().toISOString(), event_type: 'assignment', starts_at: null, due_at: new Date(Date.now() - 3600000).toISOString(), priority: 3, action_required: true, confidence: .61, review_required: true, manually_corrected: false, relevant: true, completed: false, acknowledged: false, read: false, task_updated_at: '2026-09-20T00:00:00Z', targets: [{ section: 'A', lab_group: null, course_wide: false }], ...overrides }
}

describe('F5 dashboard task card', () => {
  afterEach(cleanup)
  it('communicates every important state without color alone', () => {
    render(<DashboardTaskCard item={item()} updating={false} onChange={vi.fn()} />)
    expect(screen.getByText('! Overdue')).toBeInTheDocument()
    expect(screen.getByText('● Unread')).toBeInTheDocument()
    expect(screen.getByText('↻ Recently changed')).toBeInTheDocument()
    expect(screen.getByText('Section A')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /verify in Classroom/i })).toHaveAttribute('href', 'https://classroom.google.com/example')
  })
  it('emits local task-state changes from accessible actions', () => {
    const onChange = vi.fn()
    render(<DashboardTaskCard item={item({ due_at: new Date(Date.now() + 86400000).toISOString() })} updating={false} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Mark complete' }))
    fireEvent.click(screen.getByRole('button', { name: 'Mark read' }))
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }))
    expect(onChange).toHaveBeenNthCalledWith(1, { completed: true })
    expect(onChange).toHaveBeenNthCalledWith(2, { read: true })
    expect(onChange).toHaveBeenNthCalledWith(3, { acknowledged: true })
  })
})
