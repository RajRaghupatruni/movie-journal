export type MemoryCategory = 'movie' | 'place' | 'trip' | 'activity' | 'custom'

export interface ApiUser {
  id: string
  email: string | null
  display_name: string
  avatar_url: string | null
  timezone?: string
  is_active?: boolean
}

export interface ApiPreferences {
  timezone: string
  anniversary_notifications_enabled: boolean
  anniversary_email_enabled: boolean
  notification_hour: number
}

export interface ApiTandemPreference {
  tandem_id: string
  resurfacing_enabled: boolean
  routine_notifications_enabled: boolean
}

export interface ApiTandem {
  id: string
  name: string
  created_by: string | null
  timezone: string
  created_at: string
  updated_at: string
}

export interface ApiMember {
  user_id: string
  display_name: string
  role: string
  joined_at: string
}

export interface ApiMemory {
  id: string
  tandem_id: string
  tandem_name?: string | null
  category: MemoryCategory
  title: string
  local_date: string
  end_date?: string | null
  occurred_at: string | null
  timezone: string
  notes: string | null
  rating: number | null
  created_by: string | null
  created_at: string
  updated_at: string
  version: number
  nostalgia_eligible: boolean
  schema_version: number
  metadata: Record<string, unknown>
  participants: Array<Pick<ApiMember, 'user_id' | 'display_name'>>
  tags: string[]
  media: ApiMedia[]
  reflections?: ApiReflection[]
  my_reflection?: ApiReflection | null
  deleted_at?: string | null
  deletion_expires_at?: string | null
}

export interface ApiReflection {
  id: string
  user_id: string
  display_name: string
  rating: number | null
  note: string | null
  reaction: 'loved' | 'nostalgic' | 'funny' | 'favorite' | null
  created_at: string
  updated_at: string
}

export interface ApiAnniversary {
  memory: ApiMemory
  years_ago: number
  original_date: string
  anniversary_date: string
}

export interface ApiOnThisDay {
  today: string
  timezone: string
  anniversaries: ApiAnniversary[]
  fallback: ApiMemory | null
}

export interface ApiNotification {
  id: string
  type: string
  actor_name: string | null
  tandem_id: string | null
  tandem_name: string | null
  memory_id: string | null
  payload: Record<string, unknown>
  created_at: string
  read_at: string | null
  archived_at: string | null
}

export interface ApiMedia {
  id: string
  memory_id: string
  content_type: string
  byte_size: number
  width: number
  height: number
  created_at: string
  display_order: number
  url: string | null
}

export interface ApiMovieSearchResult {
  tmdb_id: number
  title: string
  original_title: string | null
  release_date: string | null
  release_year: number | null
  poster_url: string | null
  backdrop_url: string | null
  overview: string | null
  genres: string[]
  runtime_minutes: number | null
}

export interface ApiPlaceSearchResult {
  provider: 'geoapify'
  provider_place_id: string
  name: string
  formatted_address: string | null
  city: string | null
  region: string | null
  country: string | null
  latitude: number | null
  longitude: number | null
  category: string | null
}

export interface MemoryListParams {
  tandem_id?: string
  category?: MemoryCategory
  from_date?: string
  to_date?: string
  year?: number
  participant?: string
  rating_min?: number
  rating_max?: number
  tag?: string
  q?: string
  offset?: number
  limit?: number
}

export type MemoryInput = Omit<ApiMemory, 'id' | 'tandem_id' | 'created_by' | 'created_at' | 'updated_at' | 'version' | 'schema_version' | 'participants' | 'tags'> & {
  participant_ids: string[]
  tags: string[]
}

export type MemoryPatchInput = Partial<Omit<MemoryInput, 'category'>> & {
  expected_version: number
  category?: MemoryCategory
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : 'Request failed')
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    const isMultipart = typeof FormData !== 'undefined' && options.body instanceof FormData
    response = await fetch(path, { ...options, credentials: 'include', headers: { ...(isMultipart ? {} : { 'Content-Type': 'application/json' }), ...options.headers } })
  } catch {
    throw new ApiError(0, 'Network error. Check your connection and try again.')
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null)
  if (response.status === 401 && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('tandem:session-expired'))
  }
  if (!response.ok) throw new ApiError(response.status, body?.detail || 'Request failed')
  return body as T
}

export const tandemApi = {
  me: () => request<ApiUser>('/api/me'),
  logout: () => request<void>('/auth/logout', { method: 'POST', body: JSON.stringify({}) }),
  tandems: () => request<ApiTandem[]>('/api/me/tandems'),
  createTandem: (input: { name: string; timezone: string }) => request<ApiTandem>('/api/tandems', { method: 'POST', body: JSON.stringify(input) }),
  preferences: () => request<ApiPreferences>('/api/me/preferences'),
  updatePreferences: (input: Partial<ApiPreferences>) => request<ApiPreferences>('/api/me/preferences', { method: 'PATCH', body: JSON.stringify(input) }),
  deactivateAccount: () => request<void>('/api/me/deactivate', { method: 'POST', body: JSON.stringify({ confirmation: 'DEACTIVATE' }) }),
  deleteAccount: () => request<void>('/api/me/delete', { method: 'POST', body: JSON.stringify({ confirmation: 'DELETE' }) }),
  reactivateAccount: () => request<ApiUser>('/api/me/reactivate', { method: 'POST' }),
  globalMemories: (params: MemoryListParams = {}) => {
    const search = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') search.set(key, String(value)) })
    return request<{ items: ApiMemory[]; offset: number; limit: number; next_offset: number | null }>(`/api/me/memories${search.size ? `?${search}` : ''}`)
  },
  globalToday: (tandemId?: string) => request<ApiOnThisDay>(`/api/me/on-this-day${tandemId ? `?tandem_id=${encodeURIComponent(tandemId)}` : ''}`),
  notifications: (limit = 50) => request<{ items: ApiNotification[]; unread_count: number }>(`/api/me/notifications?limit=${limit}`),
  markNotificationRead: (id: string) => request<ApiNotification>(`/api/me/notifications/${id}/read`, { method: 'POST' }),
  markAllNotificationsRead: () => request<void>('/api/me/notifications/read-all', { method: 'POST' }),
  tandem: (tandemId: string) => request<ApiTandem>(`/api/tandems/${tandemId}`),
  tandemPreferences: (tandemId: string) => request<ApiTandemPreference>(`/api/tandems/${tandemId}/preferences`),
  updateTandemPreferences: (tandemId: string, input: Partial<ApiTandemPreference>) => request<ApiTandemPreference>(`/api/tandems/${tandemId}/preferences`, { method: 'PATCH', body: JSON.stringify(input) }),
  updateTandem: (tandemId: string, input: Partial<Pick<ApiTandem, 'name' | 'timezone'>>) => request<ApiTandem>(`/api/tandems/${tandemId}`, { method: 'PATCH', body: JSON.stringify(input) }),
  promoteMember: (tandemId: string, userId: string) => request<ApiMember>(`/api/tandems/${tandemId}/members/${userId}/promote`, { method: 'POST' }),
  demoteMember: (tandemId: string, userId: string) => request<ApiMember>(`/api/tandems/${tandemId}/members/${userId}/demote`, { method: 'POST' }),
  removeMember: (tandemId: string, userId: string) => request<void>(`/api/tandems/${tandemId}/members/${userId}`, { method: 'DELETE' }),
  leaveTandem: (tandemId: string) => request<void>(`/api/tandems/${tandemId}/leave`, { method: 'POST' }),
  deleteTandem: (tandemId: string, confirmation: string) => request<void>(`/api/tandems/${tandemId}`, { method: 'DELETE', body: JSON.stringify({ confirmation }) }),
  invitations: (tandemId: string) => request<Array<{ id: string; tandem_id: string; tandem_name: string; invited_email: string; status: string; expires_at: string; inviter_name?: string | null; created_at?: string | null }>>(`/api/tandems/${tandemId}/invitations`),
  createInvitation: (tandemId: string, invited_email: string) => request<{ reference: string; invited_email: string; memory_count?: number; earliest_memory_date?: string | null }>(`/api/tandems/${tandemId}/invitations`, { method: 'POST', body: JSON.stringify({ invited_email }) }),
  revokeInvitation: (tandemId: string, reference: string) => request<void>(`/api/tandems/${tandemId}/invitations/${encodeURIComponent(reference)}/revoke`, { method: 'POST' }),
  resendInvitation: (tandemId: string, reference: string) => request<{ reference: string; invited_email: string }>(`/api/tandems/${tandemId}/invitations/${encodeURIComponent(reference)}/resend`, { method: 'POST' }),
  invitation: (reference: string) => request<{ id: string; tandem_id: string; tandem_name: string; invited_email: string; status: string; expires_at: string; inviter_name?: string | null; memory_count?: number; earliest_memory_date?: string | null }>(`/api/invitations/${encodeURIComponent(reference)}`),
  acceptInvitation: (reference: string) => request<{ tandem_id: string; tandem_name: string; status: string }>(`/api/invitations/${encodeURIComponent(reference)}/accept`, { method: 'POST' }),
  members: (tandemId: string) => request<ApiMember[]>(`/api/tandems/${tandemId}/members`),
  onThisDay: (tandemId: string) => request<ApiOnThisDay>(`/api/tandems/${tandemId}/on-this-day`),
  memories: (tandemId: string, params: MemoryListParams = {}) => {
    const search = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') search.set(key, String(value)) })
    return request<{ items: ApiMemory[]; offset: number; limit: number; next_offset: number | null }>(`/api/tandems/${tandemId}/memories${search.size ? `?${search}` : ''}`)
  },
  memory: (tandemId: string, memoryId: string) => request<ApiMemory>(`/api/tandems/${tandemId}/memories/${memoryId}`),
  createMemory: (tandemId: string, input: MemoryInput) => request<ApiMemory>(`/api/tandems/${tandemId}/memories`, { method: 'POST', body: JSON.stringify(input) }),
  updateMemory: (tandemId: string, memoryId: string, input: MemoryPatchInput) => request<ApiMemory>(`/api/tandems/${tandemId}/memories/${memoryId}`, { method: 'PATCH', body: JSON.stringify(input) }),
  deleteMemory: (tandemId: string, memoryId: string, expectedVersion?: number) => request<void>(`/api/tandems/${tandemId}/memories/${memoryId}${expectedVersion ? `?expected_version=${expectedVersion}` : ''}`, { method: 'DELETE' }),
  deletedMemories: (tandemId: string) => request<{ items: ApiMemory[] }>(`/api/tandems/${tandemId}/memories/deleted`),
  restoreMemory: (tandemId: string, memoryId: string) => request<ApiMemory>(`/api/tandems/${tandemId}/memories/${memoryId}/restore`, { method: 'POST' }),
  permanentlyDeleteMemory: (tandemId: string, memoryId: string) => request<void>(`/api/tandems/${tandemId}/memories/${memoryId}/permanent`, { method: 'DELETE' }),
  saveReflection: (tandemId: string, memoryId: string, input: { rating?: number | null; note?: string | null; reaction?: ApiReflection['reaction'] }) => request<ApiReflection>(`/api/tandems/${tandemId}/memories/${memoryId}/reflections/me`, { method: 'PUT', body: JSON.stringify(input) }),
  deleteReflection: (tandemId: string, memoryId: string) => request<void>(`/api/tandems/${tandemId}/memories/${memoryId}/reflections/me`, { method: 'DELETE' }),
  duplicateMemories: (tandemId: string, input: { category: MemoryCategory; local_date: string; title: string; provider_id?: string }) => { const params = new URLSearchParams({ category: input.category, local_date: input.local_date, title: input.title }); if (input.provider_id) params.set('provider_id', input.provider_id); return request<Array<{ id: string; title: string; local_date: string; category: MemoryCategory }>>(`/api/tandems/${tandemId}/memories/duplicates?${params}`) },
  shuffle: (tandemId?: string, seed?: string) => request<{ memory: ApiMemory | null; message?: string }>(`/api/me/rediscovery/shuffle${tandemId ? `?tandem_id=${tandemId}` : ''}${seed ? `${tandemId ? '&' : '?'}seed=${encodeURIComponent(seed)}` : ''}`),
  yearReview: (year: number, tandemId?: string) => request<Record<string, unknown>>(`/api/me/rediscovery/year-review?year=${year}${tandemId ? `&tandem_id=${tandemId}` : ''}`),
  throwbackCollections: (tandemId?: string) => request<{ items: Array<{ key: string; title: string; memory_ids: string[] }> }>(`/api/me/rediscovery/collections${tandemId ? `?tandem_id=${tandemId}` : ''}`),
  searchMovies: (query: string) => request<{ items: ApiMovieSearchResult[] }>(`/api/integrations/movies/search?q=${encodeURIComponent(query)}`),
  movie: (tmdbId: number) => request<ApiMovieSearchResult>(`/api/integrations/movies/${tmdbId}`),
  searchPlaces: (query: string) => request<{ items: ApiPlaceSearchResult[] }>(`/api/integrations/places/search?q=${encodeURIComponent(query)}`),
  memoryMedia: (tandemId: string, memoryId: string) => request<ApiMedia[]>(`/api/tandems/${tandemId}/memories/${memoryId}/media`),
  uploadMemoryMedia: (tandemId: string, memoryId: string, files: File[]) => {
    const body = new FormData()
    files.forEach((file) => body.append('files', file, file.name))
    return request<ApiMedia[]>(`/api/tandems/${tandemId}/memories/${memoryId}/media`, { method: 'POST', body })
  },
  deleteMemoryMedia: (tandemId: string, memoryId: string, mediaId: string) => request<void>(`/api/tandems/${tandemId}/memories/${memoryId}/media/${mediaId}`, { method: 'DELETE' }),
}
