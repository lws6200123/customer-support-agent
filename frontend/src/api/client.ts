import type { ErrorEnvelope, SuccessEnvelope } from './types'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const DEFAULT_TIMEOUT_MS = 20_000

export class ApiClientError extends Error {
  readonly code: string
  readonly status: number
  readonly requestId: string | null

  constructor(message: string, code: string, status: number, requestId: string | null) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.status = status
    this.requestId = requestId
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
      signal: controller.signal,
    })
    const payload = (await response.json()) as SuccessEnvelope<T> | ErrorEnvelope
    if (!response.ok || !payload.ok) {
      const error = payload as ErrorEnvelope
      throw new ApiClientError(error.error?.message || `API request failed with HTTP ${response.status}.`, error.error?.code || 'HTTP_ERROR', response.status, error.request_id || response.headers.get('X-Request-ID'))
    }
    return payload.data
  } catch (error) {
    if (error instanceof ApiClientError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiClientError('网络请求超时，请稍后重试。', 'REQUEST_TIMEOUT', 0, null)
    }
    throw new ApiClientError('网络请求失败，请确认 FastAPI 服务正在运行。', 'NETWORK_ERROR', 0, null)
  } finally {
    window.clearTimeout(timeout)
  }
}

export function displayApiError(error: unknown): string {
  if (error instanceof ApiClientError) {
    const statusMessage = error.status === 404 ? '未找到请求的数据。' : error.status === 503 ? '服务暂时不可用，请稍后重试。' : error.message
    return `${statusMessage}${error.requestId ? ` 请求 ID：${error.requestId}` : ''}`
  }
  return '发生未知错误，请重试。'
}
