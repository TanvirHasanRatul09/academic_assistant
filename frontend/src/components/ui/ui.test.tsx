import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Button, EmptyState, ErrorState, Field, IconButton, Input, ResponsiveDataList, Switch, Tabs, Tooltip } from './index'

afterEach(() => cleanup())

describe('F2 component library', () => {
  it('exposes button state and accessible icon naming', () => {
    render(<><Button loading>Save</Button><IconButton label="Add course" icon="+" /></>)
    expect(screen.getByRole('button', { name: /please wait/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Add course' })).toBeInTheDocument()
  })

  it('wires labels, hints, and validation to form controls', () => {
    render(<Field label="Course" hint="Use the course title" error="Course is required">{({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} aria-invalid="true" />}</Field>)
    const input = screen.getByLabelText('Course')
    expect(input).toHaveAccessibleDescription('Use the course title Course is required')
    expect(screen.getByRole('alert')).toHaveTextContent('Course is required')
  })

  it('operates switch controls with a native checkbox', () => {
    const onChange = vi.fn()
    render(<Switch label="Reminders" checked={false} onChange={onChange} />)
    fireEvent.click(screen.getByRole('switch', { name: 'Reminders' }))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('supports arrow-key tab selection and focus', () => {
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => { callback(0); return 0 })
    function Example() { const [value, setValue] = useState('one'); return <Tabs label="Example tabs" value={value} onValueChange={setValue} tabs={[{ id: 'one', label: 'One', panel: 'First panel' }, { id: 'two', label: 'Two', panel: 'Second panel' }]} /> }
    render(<Example />)
    fireEvent.keyDown(screen.getByRole('tab', { name: 'One' }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'Two' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Second panel')
  })

  it('announces state patterns with suitable live semantics', () => {
    render(<><EmptyState title="No items" description="Nothing here yet" /><ErrorState title="Sync failed" description="Try again" /></>)
    expect(screen.getByRole('status')).toHaveTextContent('No items')
    expect(screen.getByRole('alert')).toHaveTextContent('Sync failed')
  })

  it('renders responsive data as a semantic list and supports empty fallback', () => {
    const { rerender } = render(<ResponsiveDataList items={[{ id: '1', title: 'Exam' }]} keyOf={(item) => item.id} renderItem={(item) => item.title} />)
    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.getByRole('listitem')).toHaveTextContent('Exam')
    rerender(<ResponsiveDataList items={[]} keyOf={(item: { id: string }) => item.id} renderItem={(item) => item.id} empty={<p>No results</p>} />)
    expect(screen.getByText('No results')).toBeInTheDocument()
  })

  it('connects tooltip descriptions without changing trigger sizing', () => {
    render(<Tooltip content="More information"><button type="button">Info</button></Tooltip>)
    expect(screen.getByRole('button', { name: 'Info' })).toHaveAccessibleDescription('More information')
    expect(screen.getByRole('tooltip')).toHaveTextContent('More information')
  })
})

