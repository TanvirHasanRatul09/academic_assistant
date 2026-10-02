import { describe, expect, it } from 'vitest'

import { apiErrorMessage } from './api'

describe('apiErrorMessage', () => {
  it('preserves plain backend errors', () => {
    expect(apiErrorMessage({ detail: 'Authentication required' })).toBe('Authentication required')
  })

  it('renders FastAPI validation errors as readable text', () => {
    expect(apiErrorMessage({ detail: [{ loc: ['query', 'course_id'], msg: 'Input should be a valid UUID' }] }))
      .toBe('course_id: Input should be a valid UUID')
  })

  it('supports the application error envelope', () => {
    expect(apiErrorMessage({ error: { message: 'Unexpected server error' } })).toBe('Unexpected server error')
  })

  it('never stringifies unknown objects into object Object', () => {
    expect(apiErrorMessage({ detail: { unexpected: true } })).toBe('Request failed')
  })
})
