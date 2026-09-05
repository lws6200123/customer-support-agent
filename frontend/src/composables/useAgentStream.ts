import { ref } from 'vue'
import { API_BASE_URL, ApiClientError } from '../api/client'
import type { AgentRunRequest, KnownSseEventType, SSEEvent } from '../api/types'

const knownEvents = new Set<KnownSseEventType>([
  'run_started', 'classification', 'tool_started', 'tool_completed',
  'decision', 'final_response', 'run_completed', 'error',
])

export function createSseParser(onEvent: (event: SSEEvent) => void) {
  let buffer = ''
  return (chunk: string, flush = false) => {
    buffer += chunk.replace(/\r\n/g, '\n')
    const blocks = buffer.split('\n\n')
    buffer = flush ? '' : blocks.pop() || ''
    for (const block of blocks) {
      const lines = block.split('\n')
      const eventName = lines.find((line) => line.startsWith('event:'))?.slice(6).trim()
      const data = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n')
      if (!eventName || !data) continue
      try {
        const payload = JSON.parse(data) as SSEEvent
        onEvent({ ...payload, event: eventName })
      } catch {
        // Ignore malformed/unknown future payloads without crashing the console.
      }
    }
  }
}

export function useAgentStream() {
  const events = ref<SSEEvent[]>([])
  const isRunning = ref(false)
  const error = ref<string | null>(null)
  let controller: AbortController | null = null

  async function run(payload: AgentRunRequest): Promise<SSEEvent[]> {
    controller?.abort()
    controller = new AbortController()
    events.value = []
    error.value = null
    isRunning.value = true
    const parser = createSseParser((event) => {
      if (knownEvents.has(event.event as KnownSseEventType)) events.value.push(event)
      if (event.event === 'error') error.value = event.detail || 'Agent 执行已安全终止。'
    })
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/agent/run/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })
      if (!response.ok) {
        let message = `Agent 执行失败，HTTP 状态码 ${response.status}。`
        try {
          const body = await response.json() as { error?: { message?: string }; request_id?: string }
          message = `${body.error?.message || message}${body.request_id ? ` 请求 ID：${body.request_id}` : ''}`
        } catch { /* keep safe HTTP message */ }
        throw new ApiClientError(message, 'STREAM_HTTP_ERROR', response.status, response.headers.get('X-Request-ID'))
      }
      if (!response.body) throw new ApiClientError('浏览器未收到 Agent 响应流。', 'STREAM_UNAVAILABLE', 0, null)
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        parser(decoder.decode(value, { stream: true }))
      }
      parser(decoder.decode(), true)
      return events.value
    } catch (caught) {
      if ((caught as DOMException).name !== 'AbortError') {
        error.value = caught instanceof Error ? caught.message : 'Agent 执行失败并已安全终止。'
      }
      return events.value
    } finally {
      isRunning.value = false
    }
  }

  function cancel() { controller?.abort() }
  return { events, isRunning, error, run, cancel }
}
