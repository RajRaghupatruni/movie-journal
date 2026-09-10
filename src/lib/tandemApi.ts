export type MemoryCategory = 'movie' | 'place' | 'trip' | 'activity' | 'custom'

export interface ApiUser {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
}

export interface ApiTandem {
  id: string
  name: string
  created_by: string
  timezone: string
  created_at: string
  updated_at: string
}

export interface ApiMember {
  user_id: string
  email: string
  display_name: string
  avatar_url: string | null
  role: string
  joined_at: string
}

export interface ApiMemory {
  id: string
  tandem_id: string
  category: MemoryCategory
  title: string
  local_date: string
  occurred_at: string | null
  timezone: string
  notes: string | null
  rating: number | null
  created_by: string
  created_at: string
  updated_at: string
  version: number
  nostalgia_eligible: boolean
  schema_version: number
  metadata: Record<string, unknown>
  participants: Array<Pick<ApiMember, 'user_id' | 'display_name' | 'email' | 'avatar_url'>>
  tags: string[]
}

export interface MemoryListParams {
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
    response = await fetch(path, { ...options, credentials: 'include', headers: { 'Content-Type': 'application/json', ...options.headers } })
  } catch {
    throw new ApiError(0, 'Network error. Check your connection and try again.')
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, body?.detail || 'Request failed')
  return body as T
}

export const tandemApi = {
  me: () => request<ApiUser>('/api/me'),
  tandems: () => request<ApiTandem[]>('/api/me/tandems'),
  members: (tandemId: string) => request<ApiMember[]>(`/api/tandems/${tandemId}/members`),
  memories: (tandemId: string, params: MemoryListParams = {}) => {
    const search = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') search.set(key, String(value)) })
    return request<{ items: ApiMemory[]; offset: number; limit: number; next_offset: number | null }>(`/api/tandems/${tandemId}/memories${search.size ? `?${search}` : ''}`)
  },
  memory: (tandemId: string, memoryId: string) => request<ApiMemory>(`/api/tandems/${tandemId}/memories/${memoryId}`),
  createMemory: (tandemId: string, input: MemoryInput) => request<ApiMemory>(`/api/tandems/${tandemId}/memories`, { method: 'POST', body: JSON.stringify(input) }),
  updateMemory: (tandemId: string, memoryId: string, input: MemoryPatchInput) => request<ApiMemory>(`/api/tandems/${tandemId}/memories/${memoryId}`, { method: 'PATCH', body: JSON.stringify(input) }),
  deleteMemory: (tandemId: string, memoryId: string, expectedVersion?: number) => request<void>(`/api/tandems/${tandemId}/memories/${memoryId}${expectedVersion ? `?expected_version=${expectedVersion}` : ''}`, { method: 'DELETE' }),
}
