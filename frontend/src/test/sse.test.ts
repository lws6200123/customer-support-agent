import { describe, expect, it } from 'vitest'
import { createSseParser } from '../composables/useAgentStream'
import type { SSEEvent } from '../api/types'

const payload = (event: string, detail: string | null = null) => JSON.stringify({ event, timestamp: '2026-09-05T00:00:00', run_id: 1, ticket_id: null, detail, intent: null, decision: null, tool: null, tool_ok: null, response: null })

describe('POST SSE parser', () => {
  it('parses normal events across chunks', () => {
    const events: SSEEvent[] = []; const parse = createSseParser((event) => events.push(event))
    parse(`event: run_started\ndata: ${payload('run_started')}\n`)
    parse(`\nevent: decision\ndata: ${payload('decision')}\n\n`)
    expect(events.map((item) => item.event)).toEqual(['run_started', 'decision'])
  })
  it('parses a safe error event', () => {
    const events: SSEEvent[] = []; const parse = createSseParser((event) => events.push(event))
    parse(`event: error\ndata: ${payload('error', 'Safe termination')}\n\n`)
    expect(events[0]).toMatchObject({ event: 'error', detail: 'Safe termination' })
  })
  it('does not crash on an unknown future event', () => {
    const events: SSEEvent[] = []; const parse = createSseParser((event) => events.push(event))
    expect(() => parse(`event: future_progress\ndata: ${payload('future_progress')}\n\n`)).not.toThrow()
    expect(events[0].event).toBe('future_progress')
  })
})
