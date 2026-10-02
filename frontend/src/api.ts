import { config } from './config'
import { clearOfflineData } from './offline'

export type SessionUser = { id: string; email: string; display_name: string; onboarding_complete: boolean }
export type Profile = { user_id: string; email: string; display_name: string; onboarding_complete: boolean; academic_level?: string | null; program?: string | null; section: string | null; lab_group: string | null; timezone: string; selected_course_ids: string[]; notification_preferences: Record<string, boolean | number>; courses?: Array<{ id: string; name: string; selected: boolean; enrollment_status?: string; eligible?: boolean }>; classroom_connected?: boolean; last_successful_sync_at?: string | null }
export type ShellData = { user: SessionUser; unread_notification_count: number; latest_sync: SyncRun | null }
export type SyncRun = { id:string; status:'running'|'succeeded'|'partial'|'failed'; started_at:string; finished_at:string|null; items_seen:number; items_changed:number; safe_error_code:string|null; courses_processed:number; courses_total:number; current_phase:string|null; timing_metrics:Record<string,number>; heartbeat_at:string|null; failed_courses:Array<{course:string;code:string}> }
export type DashboardView = 'all'|'today'|'tomorrow'|'week'|'upcoming'|'deadlines'|'exams'|'notices'|'recent'
export type DashboardEventType = 'assignment'|'exam'|'notice'|'material'|'other'
export type DashboardFilters = { view?: DashboardView; courseId?: string; eventType?: DashboardEventType; completed?: boolean; priority?: number; source?:'all'|'classroom'|'manual'; limit?: number }
export type DashboardTarget = { section: string|null; lab_group: string|null; academic_level?:string|null; program?:string|null; course_wide: boolean }
export type DashboardItem = { task_id:string; event_id:string; course_id:string|null; course_name:string; title:string; body:string|null; source_type:string; source_url:string|null; source_created_at:string; source_updated_at:string; event_type:DashboardEventType; starts_at:string|null; due_at:string|null; priority:number; action_required:boolean; confidence:number; review_required:boolean; manually_corrected:boolean; relevant:boolean; relevance_reason?:string; completed:boolean; acknowledged:boolean; read:boolean; task_updated_at:string; targets:DashboardTarget[]; source_kind?:'classroom'|'manual' }
export type DashboardData = { generated_at:string; timezone:string; items:DashboardItem[]; courses:Array<{id:string;name:string}> }
export type SavedTaskState = { completed:boolean; acknowledged:boolean; read:boolean; updated_at:string }
export type AppNotification = { id:string; kind:string; created_at:string; read_at:string|null; dismissed_at:string|null; task_id:string; title:string; course_name:string; event_type:string; priority:number; due_at:string|null; source_url:string }
export type NotificationPreferences = { assignments:boolean; exams:boolean; notices:boolean; minimum_priority:number; courses:Array<{id:string;name:string;enabled:boolean}> }
export type GeminiStatus = 'configured'|'not_configured'|'reachable'|'invalid_credentials'|'rate_limited'|'quota_exceeded'|'timeout'|'network_error'|'model_unavailable'|'provider_error'|'blocked_response'|'malformed_response'
export type AssistantAction = { label:string; url:string; kind:'pdf'|'attachment'|'classroom' }
export type AssistantItem = { title:string; course_name:string; item_subtype:string; completed:boolean|null; starts_at?:string|null; due_at?:string|null; source_kind:'classroom'|'manual'; source_url?:string|null }
export type AssistantResponse = { answer:string; mode:'gemini'|'local'; gemini_status?:GeminiStatus; tool:'get_tasks_by_date'|'get_upcoming_deadlines'|'get_exams'|'search_academic_content'; sources:Array<{title:string;course_name:string;source_url:string|null;event_type:string;item_subtype?:string;completed?:boolean|null;starts_at?:string|null;due_at:string|null;actions?:AssistantAction[]}>; last_sync_at:string|null; data_available:boolean; answer_status?:'exact_match'|'multiple_matches'|'ambiguous_course'|'no_exact_match'|'partial_sync'|'stale_data'; intent?:string; item?:AssistantItem|null; possible_matches?:AssistantItem[] }

export class ApiError extends Error { constructor(message:string, public readonly status:number){ super(message); this.name='ApiError' } }
type ApiErrorBody = { detail?: unknown; error?: { message?: unknown } }

function errorDetailMessage(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((entry) => {
      if (typeof entry === 'string') return entry
      if (!entry || typeof entry !== 'object') return null
      const item = entry as { msg?: unknown; message?: unknown; loc?: unknown }
      const message = typeof item.msg === 'string' ? item.msg : typeof item.message === 'string' ? item.message : null
      if (!message) return null
      const location = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'query' && part !== 'body').join('.') : ''
      return location ? `${location}: ${message}` : message
    }).filter((message): message is string => Boolean(message))
    return messages.length ? messages.join('; ') : null
  }
  if (detail && typeof detail === 'object') {
    const item = detail as { message?: unknown; msg?: unknown; code?: unknown }
    if (typeof item.message === 'string') return item.message
    if (typeof item.msg === 'string') return item.msg
    if (typeof item.code === 'string') return item.code
  }
  return null
}

export function apiErrorMessage(body: unknown): string {
  if (!body || typeof body !== 'object') return 'Request failed'
  const errorBody = body as ApiErrorBody
  return errorDetailMessage(errorBody.detail) ?? errorDetailMessage(errorBody.error?.message) ?? 'Request failed'
}

async function request<T>(path:string, init?:RequestInit):Promise<T>{ let response:Response; try { response=await fetch(config.apiBaseUrl+path,{...init,credentials:'include',headers:{'Content-Type':'application/json',...init?.headers}}) } catch { throw new ApiError('Network unavailable',0) } if(!response.ok){ const body:unknown=await response.json().catch(()=>null); throw new ApiError(apiErrorMessage(body),response.status) } return response.status===204 ? undefined as T : response.json() }
async function csrfHeaders(){ const value=await request<{csrf_token:string}>('/api/auth/csrf'); return {'X-CSRF-Token':value.csrf_token} }
export async function beginGoogleAuth(reauthenticate=false){ const path=reauthenticate?'/api/auth/google/reauth':'/api/auth/google/start'; const value=await request<{authorization_url:string}>(path); window.location.assign(value.authorization_url) }
export async function reconnectGoogle(){ const value=await request<{authorization_url:string}>('/api/auth/google/reconnect'); window.location.assign(value.authorization_url) }
export const getCurrentUser=()=>request<SessionUser>('/api/auth/me')
export const getShell=()=>request<ShellData>('/api/shell')
let profileCache: { value: Profile; expiresAt: number } | null = null
let profileRequest: Promise<Profile> | null = null
export function getProfile(){
  if(profileCache && profileCache.expiresAt>Date.now()) return Promise.resolve(profileCache.value)
  if(profileRequest) return profileRequest
  profileRequest=request<Profile>('/api/auth/profile').then((value)=>{ profileCache={value,expiresAt:Date.now()+15_000}; return value }).finally(()=>{ profileRequest=null })
  return profileRequest
}
export function prefetchProfile(){ return getProfile() }
export const getCourses=()=>request<Array<{id:string;name:string;selected:boolean}>>('/api/auth/courses')
export async function saveProfile(profile:Omit<Profile,'user_id'|'email'|'display_name'|'onboarding_complete'|'courses'|'classroom_connected'|'last_successful_sync_at'>){ const saved=await request<Profile>('/api/auth/profile',{method:'PUT',headers:await csrfHeaders(),body:JSON.stringify(profile)}); profileCache={value:saved,expiresAt:Date.now()+15_000}; return saved }
async function finishAccountExit(action:()=>Promise<unknown>){ try{await action()}finally{await clearOfflineData();window.location.assign('/')} }
export const logout=()=>finishAccountExit(async()=>request('/api/auth/logout',{method:'POST',headers:await csrfHeaders()}))
export const disconnectAccount=()=>finishAccountExit(async()=>request('/api/auth/connection',{method:'DELETE',headers:await csrfHeaders()}))
export const deleteAccount=()=>finishAccountExit(async()=>request('/api/auth/account',{method:'DELETE',headers:await csrfHeaders()}))
export const getSyncStatus=()=>request<{latest:SyncRun|null}>('/api/sync/status')
export async function synchronize(){ return request<SyncRun>('/api/sync',{method:'POST',headers:await csrfHeaders()}) }
export async function getDashboard(filters:DashboardFilters={}){ const query=new URLSearchParams(); Object.entries(filters).forEach(([key,value])=>{if(value!==undefined&&value!==''&&!(key==='source'&&value==='all'))query.set(key==='courseId'?'course_id':key==='eventType'?'event_type':key,String(value))}); return request<DashboardData>(`/api/dashboard${query.size?`?${query}`:''}`) }
export async function updateTaskState(taskId:string,patch:Partial<Pick<DashboardItem,'completed'|'acknowledged'|'read'>>,expectedUpdatedAt?:string){ return request<SavedTaskState>(`/api/dashboard/tasks/${taskId}`,{method:'PATCH',headers:await csrfHeaders(),body:JSON.stringify({...patch,expected_updated_at:expectedUpdatedAt})}) }
export async function getNotifications(){ return request<{items:AppNotification[];unread_count:number}>('/api/notifications') }
export const getNotificationUnreadCount=()=>request<{unread_count:number}>('/api/notifications/unread-count')
export async function markNotificationRead(id:string){ await request(`/api/notifications/${id}/read`,{method:'POST',headers:await csrfHeaders()}) }
export async function markAllNotificationsRead(){ await request('/api/notifications/actions/read-all',{method:'POST',headers:await csrfHeaders()}) }
export async function dismissNotification(id:string){ await request(`/api/notifications/${id}`,{method:'DELETE',headers:await csrfHeaders()}) }
export const getNotificationPreferences=()=>request<NotificationPreferences>('/api/notifications/preferences')
export async function saveNotificationPreferences(preferences:Omit<NotificationPreferences,'courses'>&{course_preferences:Record<string,boolean>}){ return request<NotificationPreferences>('/api/notifications/preferences',{method:'PUT',headers:await csrfHeaders(),body:JSON.stringify(preferences)}) }
export async function askAssistant(message:string,history:Array<{role:'user'|'assistant';content:string}> = []){ return request<AssistantResponse>('/api/assistant/query',{method:'POST',headers:await csrfHeaders(),body:JSON.stringify({message,history})}) }





export type RelevanceDebugItem = { event_id:string; course:string; title:string; relevant:boolean; reason:string; review_required:boolean; targeting:Record<string,string[]|boolean> }
export const getRelevanceDebug=()=>request<RelevanceDebugItem[]>('/api/dashboard/relevance-debug')






export type PersonalTask = { id:string; user_id:string; course_id:string|null; course_name:string|null; title:string; details:string|null; event_type:DashboardEventType; starts_at:string|null; due_at:string|null; priority:number; section:string|null; lab_group:string|null; completed:boolean; created_at:string; updated_at:string; source_kind:'manual' }
export type PersonalTaskInput = Pick<PersonalTask,'title'|'details'|'course_id'|'event_type'|'starts_at'|'due_at'|'priority'|'section'|'lab_group'|'completed'>
export const getPersonalTasks=()=>request<PersonalTask[]>('/api/personal-tasks')
export async function createPersonalTask(payload:PersonalTaskInput){ return request<PersonalTask>('/api/personal-tasks',{method:'POST',headers:await csrfHeaders(),body:JSON.stringify(payload)}) }
export async function updatePersonalTask(id:string,payload:Partial<PersonalTaskInput>){ return request<PersonalTask>(`/api/personal-tasks/${id}`,{method:'PATCH',headers:await csrfHeaders(),body:JSON.stringify(payload)}) }
export async function deletePersonalTask(id:string){ return request<void>(`/api/personal-tasks/${id}`,{method:'DELETE',headers:await csrfHeaders()}) }
