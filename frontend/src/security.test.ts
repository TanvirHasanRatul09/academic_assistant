import { describe, expect, it } from 'vitest'

import { safeExternalUrl } from './security'

describe('untrusted external links', () => {
  it('allows HTTPS sources and rejects script, data, and malformed URLs', () => {
    expect(safeExternalUrl('https://classroom.google.com/example')).toBe('https://classroom.google.com/example')
    expect(safeExternalUrl('javascript:alert(1)')).toBeNull()
    expect(safeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(safeExternalUrl('not a URL')).toBeNull()
  })
})
