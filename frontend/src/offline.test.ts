import { describe, expect, it } from 'vitest'

import type { DashboardData, DashboardItem } from './api'
import { filterOfflineDashboardData } from './offline'

const baseItem: DashboardItem = {
  task_id: 'task-1',
  event_id: 'event-1',
  course_id: 'course-a',
  course_name: 'Algorithms',
  title: 'Submit assignment',
  body: null,
  source_type: 'coursework',
  source_url: 'https://classroom.google.com/example',
  source_created_at: '2026-09-25T12:00:00Z',
  source_updated_at: '2026-09-25T12:00:00Z',
  event_type: 'assignment',
  starts_at: null,
  due_at: '2026-09-26T12:00:00Z',
  priority: 2,
  action_required: true,
  confidence: 0.9,
  review_required: false,
  manually_corrected: false,
  relevant: true,
  completed: false,
  acknowledged: false,
  read: false,
  task_updated_at: '2026-09-25T12:00:00Z',
  source_kind: 'classroom', targets: [{ section: null, lab_group: null, course_wide: true }],
}

function item(overrides: Partial<DashboardItem>): DashboardItem {
  return { ...baseItem, ...overrides }
}

const data: DashboardData = {
  generated_at: '2026-09-26T00:00:00Z',
  timezone: 'Asia/Dhaka',
  courses: [
    { id: 'course-a', name: 'Algorithms' },
    { id: 'course-b', name: 'Databases' },
  ],
  items: [
    baseItem,
    item({
      task_id: 'task-2',
      event_id: 'event-2',
      course_id: 'course-b',
      course_name: 'Databases',
      title: 'Tomorrow exam',
      event_type: 'exam',
      due_at: '2026-09-27T12:00:00Z',
      priority: 3,
    }),
    item({
      task_id: 'task-3',
      event_id: 'event-3',
      title: 'Completed work',
      completed: true,
      due_at: '2026-09-28T12:00:00Z',
    }),
  ],
}

const now = new Date('2026-09-26T00:00:00Z')

describe('offline dashboard queries', () => {
  it('uses the saved user timezone for today and tomorrow', () => {
    expect(filterOfflineDashboardData(data, { view: 'today' }, now).items.map((entry) => entry.task_id))
      .toEqual(['task-1'])
    expect(filterOfflineDashboardData(data, { view: 'tomorrow' }, now).items.map((entry) => entry.task_id))
      .toEqual(['task-2'])
  })

  it('supports week, unfinished, exam, and course filtering locally', () => {
    expect(filterOfflineDashboardData(data, { view: 'week', completed: false }, now).items)
      .toHaveLength(2)
    expect(filterOfflineDashboardData(data, { view: 'exams' }, now).items.map((entry) => entry.task_id))
      .toEqual(['task-2'])
    expect(filterOfflineDashboardData(data, { view: 'all', courseId: 'course-b' }, now).items)
      .toHaveLength(1)
  })

  it('supports upcoming deadlines locally', () => {
    expect(filterOfflineDashboardData(data, { view: 'upcoming' }, now).items)
      .toHaveLength(3)
  })

  it('answers supported questions from a cached snapshot', async () => {
    const { answerFromOfflineSnapshot } = await import('./offline')
    const result = answerFromOfflineSnapshot(data, 'Show my upcoming exams', '2026-09-25T12:00:00Z', now)
    expect(result.mode).toBe('local')
    expect(result.tool).toBe('get_exams')
    expect(result.sources.map((source) => source.title)).toEqual(['Tomorrow exam'])
  })})

