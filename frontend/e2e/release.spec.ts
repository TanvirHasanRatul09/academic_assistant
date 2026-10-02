import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const user = { id: 'synthetic-user', email: 'student@example.test', display_name: 'Demo Student', onboarding_complete: true }
const dashboard = {
  generated_at: '2026-09-27T12:00:00Z',
  timezone: 'Asia/Dhaka',
  courses: [{ id: 'course-1', name: 'Synthetic Physics' }],
  items: [{
    task_id: 'task-1', event_id: 'event-1', course_id: 'course-1', course_name: 'Synthetic Physics',
    title: 'Synthetic lab final', body: 'Practice data only.', source_type: 'coursework',
    source_url: 'https://classroom.google.com/example', source_created_at: '2026-09-26T10:00:00Z',
    source_updated_at: '2026-09-27T10:00:00Z', event_type: 'exam', starts_at: null,
    due_at: '2026-09-29T10:00:00Z', priority: 3, action_required: true, confidence: .95,
    review_required: false, manually_corrected: false, relevant: true, completed: false,
    acknowledged: false, read: false, task_updated_at: '2026-09-27T10:00:00Z',
    targets: [{ section: 'A', lab_group: 'A1', course_wide: false }],
  }],
}

async function mockApi(page: Page, authenticated = true) {
  await page.route('http://localhost:8000/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path === '/api/auth/me') return route.fulfill({ status: authenticated ? 200 : 401, json: authenticated ? user : { detail: 'Authentication required' } })
    if (path === '/api/notifications/unread-count') return route.fulfill({ json: { unread_count: 2 } })
    if (path === '/api/sync/status') return route.fulfill({ json: { latest: { id: 'sync-1', status: 'succeeded', started_at: '2026-09-27T11:59:00Z', finished_at: '2026-09-27T12:00:00Z', items_seen: 8, items_changed: 2, error_code: null } } })
    if (path === '/api/dashboard') return route.fulfill({ json: dashboard })
    if (path === '/api/sync' && route.request().method() === 'POST') return route.fulfill({ json: { id: 'sync-2', status: 'succeeded', started_at: '2026-09-27T12:01:00Z', finished_at: '2026-09-27T12:01:02Z', items_seen: 8, items_changed: 0, error_code: null } })
    if (path === '/api/auth/csrf') return route.fulfill({ json: { csrf_token: 'synthetic-csrf' } })
    if (path.startsWith('/api/dashboard/tasks/')) return route.fulfill({ json: { completed: true, acknowledged: false, read: true, updated_at: '2026-09-27T12:02:00Z' } })
    return route.fulfill({ status: 404, json: { detail: 'Synthetic endpoint not configured' } })
  })
}

async function goToSpaRoute(page: Page, path: string) {
  await page.goto('/')
  await page.evaluate((route) => { history.pushState({}, '', route); window.dispatchEvent(new PopStateEvent('popstate')) }, path)
}

test('public sign-in return is accessible, secure-looking, and overflow-free', async ({ page }, testInfo) => {
  await mockApi(page, false)
  await page.goto('/?reason=session_expired')
  await expect(page.getByRole('heading', { name: /without the noise/i })).toBeVisible()
  await expect(page.getByText(/session ended safely/i)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible()
  await expect(page.locator('.ambient-background')).toHaveAttribute('aria-hidden', 'true')
  const violations = await new AxeBuilder({ page }).analyze()
  expect(violations.violations.filter((item) => ['critical', 'serious'].includes(item.impact ?? ''))).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  if (testInfo.project.name === 'chrome') await page.screenshot({ path: '../docs/frontend-f10-synthetic-desktop.png', fullPage: true })
  if (testInfo.project.name === 'mobile-chrome') await page.screenshot({ path: '../docs/frontend-f10-synthetic-mobile.png', fullPage: true })
})

test('reduced motion keeps ambient content visible without continuous animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApi(page, false)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /without the noise/i })).toBeVisible()
  const ambientMotion = await page.locator('.ambient-mesh').evaluate((element) => {
    const style = getComputedStyle(element)
    const durationSeconds = Number.parseFloat(style.animationDuration)
    return { durationSeconds, iterations: style.animationIterationCount }
  })
  expect(ambientMotion.iterations).toBe('1')
  expect(ambientMotion.durationSeconds).toBeLessThanOrEqual(.00001)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('authenticated dashboard filters, sync, task state, navigation, and session expiry', async ({ page }) => {
  await mockApi(page)
  await goToSpaRoute(page, '/dashboard?view=all')
  await expect(page.getByRole('heading', { name: 'Synthetic lab final' })).toBeVisible()
  await page.getByLabel('Event type').selectOption('exam')
  await expect(page).toHaveURL(/type=exam/)
  await page.getByRole('button', { name: 'Mark complete' }).click()
  await expect(page.getByText('✓ Completed')).toBeVisible()
  await goToSpaRoute(page, '/assistant')
  await expect(page.getByRole('heading', { name: 'Academic assistant' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  const violations = await new AxeBuilder({ page }).analyze()
  expect(violations.violations.filter((item) => ['critical', 'serious'].includes(item.impact ?? ''))).toEqual([])
})

