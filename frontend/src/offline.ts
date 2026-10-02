import type {
  DashboardData,
  DashboardFilters,
  DashboardItem,
  SessionUser,
  SavedTaskState,
} from './api'

const DATABASE_NAME = 'academic-assistant-offline'
const DATABASE_VERSION = 2
const SNAPSHOTS = 'snapshots'
const QUEUE = 'task-change-queue'
const META = 'meta'
const CONFLICTS = 'task-change-conflicts'

export type TaskStatePatch = Partial<Pick<DashboardItem, 'completed' | 'acknowledged' | 'read'>>

export type QueuedTaskUpdate = {
  key: string
  userId: string
  taskId: string
  patch: TaskStatePatch
  expectedUpdatedAt: string
  queuedAt: string
}
export type OfflineConflict = {
  key: string
  userId: string
  taskId: string
  title: string
  courseName: string
  patch: TaskStatePatch
  serverState: SavedTaskState
  detectedAt: string
}

type SnapshotRecord = {
  userId: string
  data: DashboardData
  cachedAt: string
  lastSuccessfulSyncAt: string | null
}

type MetaRecord = {
  key: string
  value: unknown
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!('indexedDB' in window)) {
      reject(new Error('Offline storage is not supported by this browser.'))
      return
    }
    const request = window.indexedDB.open(DATABASE_NAME, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(SNAPSHOTS)) {
        database.createObjectStore(SNAPSHOTS, { keyPath: 'userId' })
      }
      if (!database.objectStoreNames.contains(QUEUE)) {
        database.createObjectStore(QUEUE, { keyPath: 'key' })
      }
      if (!database.objectStoreNames.contains(META)) {
        database.createObjectStore(META, { keyPath: 'key' })
      }
      if (!database.objectStoreNames.contains(CONFLICTS)) {
        database.createObjectStore(CONFLICTS, { keyPath: 'key' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Could not open offline storage.'))
    request.onblocked = () => reject(new Error('Offline storage upgrade is blocked by another tab.'))
  })
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Offline storage request failed.'))
  })
}

async function getRecord<T>(storeName: string, key: IDBValidKey): Promise<T | undefined> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(storeName, 'readonly')
    return await requestResult(transaction.objectStore(storeName).get(key)) as T | undefined
  } finally {
    database.close()
  }
}

async function putRecord(storeName: string, value: unknown): Promise<void> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(storeName, 'readwrite')
    await requestResult(transaction.objectStore(storeName).put(value))
  } finally {
    database.close()
  }
}

async function deleteRecord(storeName: string, key: IDBValidKey): Promise<void> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(storeName, 'readwrite')
    await requestResult(transaction.objectStore(storeName).delete(key))
  } finally {
    database.close()
  }
}

async function allRecords<T>(storeName: string): Promise<T[]> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(storeName, 'readonly')
    return await requestResult(transaction.objectStore(storeName).getAll()) as T[]
  } finally {
    database.close()
  }
}

async function clearUserStores(): Promise<void> {
  const database = await openDatabase()
  try {
    const transaction = database.transaction([SNAPSHOTS, QUEUE, META, CONFLICTS], 'readwrite')
    transaction.objectStore(SNAPSHOTS).clear()
    transaction.objectStore(QUEUE).clear()
    transaction.objectStore(META).clear()
    transaction.objectStore(CONFLICTS).clear()
    await new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error ?? new Error('Could not clear offline data.'))
      transaction.onabort = () => reject(transaction.error ?? new Error('Could not clear offline data.'))
    })
  } finally {
    database.close()
  }
}

export async function setActiveOfflineUser(user: SessionUser): Promise<void> {
  const current = await getRecord<MetaRecord>(META, 'active-user-id')
  if (typeof current?.value === 'string' && current.value !== user.id) {
    await clearUserStores()
  }
  await putRecord(META, { key: 'active-user-id', value: user.id } satisfies MetaRecord)
  await putRecord(META, {
    key: 'cached-session-user',
    value: {
      id: user.id,
      email: user.email,
      display_name: user.display_name,
      onboarding_complete: user.onboarding_complete,
    } satisfies SessionUser,
  } satisfies MetaRecord)
}

export async function getCachedSessionUser(): Promise<SessionUser | null> {
  const record = await getRecord<MetaRecord>(META, 'cached-session-user')
  return record?.value && typeof record.value === 'object' ? record.value as SessionUser : null
}

export async function clearOfflineData(): Promise<void> {
  if (!('indexedDB' in window)) return
  await clearUserStores()
}

export async function cacheDashboardSnapshot(
  userId: string,
  data: DashboardData,
  lastSuccessfulSyncAt: string | null,
): Promise<void> {
  await putRecord(SNAPSHOTS, {
    userId,
    data,
    cachedAt: new Date().toISOString(),
    lastSuccessfulSyncAt,
  } satisfies SnapshotRecord)
}

export async function getCachedSnapshot(userId: string): Promise<SnapshotRecord | null> {
  return (await getRecord<SnapshotRecord>(SNAPSHOTS, userId)) ?? null
}

function localDayOrdinal(value: string | Date, timezone: string): number {
  const date = typeof value === 'string' ? new Date(value) : value
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).formatToParts(date)
  const number = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value ?? 0)
  return Date.UTC(number('year'), number('month') - 1, number('day')) / 86_400_000
}

function matchesView(
  item: DashboardItem,
  filters: DashboardFilters,
  data: DashboardData,
  now: Date,
): boolean {
  const nowTime = now.getTime()
  const eventValue = item.due_at ?? item.starts_at
  const eventOrdinal = eventValue ? localDayOrdinal(eventValue, data.timezone) : null
  const todayOrdinal = localDayOrdinal(now, data.timezone)

  if (filters.view === 'today') return eventOrdinal === todayOrdinal
  if (filters.view === 'tomorrow') return eventOrdinal === todayOrdinal + 1
  if (filters.view === 'week') {
    return eventOrdinal !== null && eventOrdinal >= todayOrdinal && eventOrdinal <= todayOrdinal + 6
  }
  if (filters.view === 'upcoming' || filters.view === 'deadlines') {
    return Boolean(item.due_at && new Date(item.due_at).getTime() >= nowTime)
  }
  if (filters.view === 'exams') return item.event_type === 'exam'
  if (filters.view === 'notices') return item.event_type === 'notice'
  if (filters.view === 'recent') {
    return new Date(item.source_updated_at).getTime() >= nowTime - (7 * 86_400_000)
  }
  return true
}

export function filterOfflineDashboardData(
  data: DashboardData,
  filters: DashboardFilters,
  now = new Date(),
): DashboardData {
  const items = data.items.filter((item) =>
    item.relevant
    && matchesView(item, filters, data, now)
    && (!filters.courseId || item.course_id === filters.courseId)
    && (!filters.eventType || item.event_type === filters.eventType)
    && (filters.completed === undefined || item.completed === filters.completed)
    && (filters.priority === undefined || item.priority === filters.priority)
    && (!filters.source || filters.source === 'all' || (item.source_kind ?? 'classroom') === filters.source)
  )
  items.sort((left, right) =>
    Number(left.completed) - Number(right.completed)
    || right.priority - left.priority
    || new Date(left.due_at ?? left.starts_at ?? '9999-12-31').getTime()
      - new Date(right.due_at ?? right.starts_at ?? '9999-12-31').getTime()
  )
  return { ...data, items: items.slice(0, 100) }
}
export async function queryOfflineDashboard(
  userId: string,
  filters: DashboardFilters,
): Promise<{ data: DashboardData; cachedAt: string; lastSuccessfulSyncAt: string | null } | null> {
  const snapshot = await getCachedSnapshot(userId)
  if (!snapshot) return null
  const data = filterOfflineDashboardData(snapshot.data, filters)
  return {
    data,
    cachedAt: snapshot.cachedAt,
    lastSuccessfulSyncAt: snapshot.lastSuccessfulSyncAt,
  }
}

export async function queueTaskUpdate(
  userId: string,
  item: DashboardItem,
  patch: TaskStatePatch,
): Promise<void> {
  const key = `${userId}:${item.task_id}`
  const existing = await getRecord<QueuedTaskUpdate>(QUEUE, key)
  await putRecord(QUEUE, {
    key,
    userId,
    taskId: item.task_id,
    patch: { ...existing?.patch, ...patch },
    expectedUpdatedAt: existing?.expectedUpdatedAt ?? item.task_updated_at,
    queuedAt: new Date().toISOString(),
  } satisfies QueuedTaskUpdate)
  await applyTaskStateToSnapshot(userId, item.task_id, patch)
}

export async function getQueuedTaskUpdates(userId: string): Promise<QueuedTaskUpdate[]> {
  const records = await allRecords<QueuedTaskUpdate>(QUEUE)
  return records.filter((record) => record.userId === userId)
}

export async function removeQueuedTaskUpdate(key: string): Promise<void> {
  await deleteRecord(QUEUE, key)
}
export async function saveOfflineConflict(userId: string, change: QueuedTaskUpdate, serverItem: DashboardItem): Promise<void> {
  await putRecord(CONFLICTS, {
    key: change.key,
    userId,
    taskId: change.taskId,
    title: serverItem.title,
    courseName: serverItem.course_name,
    patch: change.patch,
    serverState: {
      completed: serverItem.completed,
      acknowledged: serverItem.acknowledged,
      read: serverItem.read,
      updated_at: serverItem.task_updated_at,
    },
    detectedAt: new Date().toISOString(),
  } satisfies OfflineConflict)
}

export async function getOfflineConflicts(userId: string): Promise<OfflineConflict[]> {
  return (await allRecords<OfflineConflict>(CONFLICTS)).filter((conflict) => conflict.userId === userId)
}

export async function removeOfflineConflict(key: string): Promise<void> {
  await deleteRecord(CONFLICTS, key)
}

export async function applyTaskStateToSnapshot(
  userId: string,
  taskId: string,
  patch: TaskStatePatch,
  updatedAt?: string,
): Promise<void> {
  const snapshot = await getCachedSnapshot(userId)
  if (!snapshot) return
  snapshot.data = {
    ...snapshot.data,
    items: snapshot.data.items.map((item) =>
      item.task_id === taskId
        ? { ...item, ...patch, task_updated_at: updatedAt ?? item.task_updated_at }
        : item
    ),
  }
  snapshot.cachedAt = new Date().toISOString()
  await putRecord(SNAPSHOTS, snapshot)
}

export async function getOfflineStorageStatus(): Promise<{
  userId: string | null
  cachedAt: string | null
  lastSuccessfulSyncAt: string | null
  queuedChanges: number
  conflicts: number
}> {
  const active = await getRecord<MetaRecord>(META, 'active-user-id')
  const userId = typeof active?.value === 'string' ? active.value : null
  const snapshot = userId ? await getCachedSnapshot(userId) : null
  const queue = userId ? await getQueuedTaskUpdates(userId) : []
  const conflicts = userId ? await getOfflineConflicts(userId) : []
  return {
    userId,
    cachedAt: snapshot?.cachedAt ?? null,
    lastSuccessfulSyncAt: snapshot?.lastSuccessfulSyncAt ?? null,
    queuedChanges: queue.length,
    conflicts: conflicts.length,
  }
}




export function answerFromOfflineSnapshot(
  data: DashboardData,
  message: string,
  lastSuccessfulSyncAt: string | null,
  now = new Date(),
): import('./api').AssistantResponse {
  const normalized = message.toLowerCase()
  const requestedSubtype = /\blab\s+final\b/.test(normalized) ? 'lab_final'
    : /\bquiz(?:zes)?\b/.test(normalized) ? 'quiz'
    : /\b(?:midterm|mid-term|mid exam)\b/.test(normalized) ? 'midterm'
    : /\btheory\s+final\b/.test(normalized) ? 'theory_final'
    : null
  const subtypeOf = (item: DashboardItem) => {
    const text = `${item.title} ${item.body ?? ''}`.toLowerCase()
    if (/\blab\s+final\b/.test(text)) return 'lab_final'
    if (/\bquiz(?:zes)?\b/.test(text)) return 'quiz'
    if (/\b(?:midterm|mid-term|mid exam)\b/.test(text)) return 'midterm'
    if (/\btheory\s+final\b/.test(text)) return 'theory_final'
    return item.event_type
  }
  const courseMatch = (item: DashboardItem) => {
    if (/\bcse\s*3208\b|\bai\b/.test(normalized)) return /\bcse\s*3208\b/.test(item.course_name.toLowerCase())
    const code = normalized.match(/\b[a-z]{2,6}\s*\d{3,5}\b/)?.[0].replace(/\s+/g, '')
    return !code || item.course_name.toLowerCase().replace(/\s+/g, '').includes(code)
  }
  const exactItems = (values: DashboardItem[]) => values.filter((item) => courseMatch(item) && (!requestedSubtype || subtypeOf(item) === requestedSubtype))
  let tool: import('./api').AssistantResponse['tool'] = 'search_academic_content'
  let items: DashboardItem[]
  if (normalized.includes('tomorrow')) {
    tool = 'get_tasks_by_date'
    items = exactItems(filterOfflineDashboardData(data, { view: 'tomorrow' }, now).items)
  } else if (normalized.includes('today')) {
    tool = 'get_tasks_by_date'
    items = exactItems(filterOfflineDashboardData(data, { view: 'today' }, now).items)
  } else if (normalized.includes('week')) {
    tool = 'get_tasks_by_date'
    items = exactItems(filterOfflineDashboardData(data, { view: 'week' }, now).items)
  } else if (/exam|quiz|test/.test(normalized)) {
    tool = 'get_exams'
    items = exactItems(filterOfflineDashboardData(data, { view: 'exams' }, now).items)
  } else if (/deadline|due|upcoming/.test(normalized)) {
    tool = 'get_upcoming_deadlines'
    items = exactItems(filterOfflineDashboardData(data, { view: 'upcoming' }, now).items)
  } else {
    const terms = normalized.split(/\W+/).filter((term) => term.length > 2 && !['find', 'show', 'tell', 'about', 'please', 'classroom'].includes(term))
    items = data.items.filter((item) => {
      const text = `${item.title} ${item.body ?? ''} ${item.course_name}`.toLowerCase()
      return item.relevant && courseMatch(item) && (!requestedSubtype || subtypeOf(item) === requestedSubtype) && terms.length > 0 && terms.every((term) => text.includes(term))
    }).slice(0, 25)
  }
  const answer = items.length === 0
    ? 'I could not find matching information in the offline Classroom snapshot. Connect to the internet and sync to refresh it.'
    : `I found ${items.length} result${items.length === 1 ? '' : 's'} in your offline snapshot:\n${items.slice(0, 10).map((item) => `• ${item.title} — ${item.course_name}${item.completed ? ' (completed)' : ''}`).join('\n')}`
  return {
    answer,
    mode: 'local',
    tool,
    sources: items.slice(0, 25).map((item) => ({ title: item.title, course_name: item.course_name, source_url: item.source_url, event_type: item.event_type, item_subtype: subtypeOf(item), completed: item.completed, starts_at: item.starts_at, due_at: item.due_at })),
    last_sync_at: lastSuccessfulSyncAt,
    data_available: items.length > 0,
    answer_status: items.length === 0 ? 'no_exact_match' : items.length === 1 ? 'exact_match' : 'multiple_matches',
    item: items.length === 1 ? { title: items[0]!.title, course_name: items[0]!.course_name, item_subtype: subtypeOf(items[0]!), completed: items[0]!.completed, starts_at: items[0]!.starts_at, due_at: items[0]!.due_at, source_kind: items[0]!.source_kind ?? 'classroom', source_url: items[0]!.source_url } : null,
    possible_matches: [],
  }
}

export async function askOfflineAssistant(userId: string, message: string): Promise<import('./api').AssistantResponse | null> {
  const snapshot = await getCachedSnapshot(userId)
  return snapshot ? answerFromOfflineSnapshot(snapshot.data, message, snapshot.lastSuccessfulSyncAt) : null
}

