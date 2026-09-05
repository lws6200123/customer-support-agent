import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError, apiRequest } from '../api/client'

afterEach(() => vi.unstubAllGlobals())

describe('API client envelopes', () => {
  it('returns data from a successful envelope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, data: { total: 7 }, request_id: 'req-1' }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    await expect(apiRequest<{ total: number }>('/test')).resolves.toEqual({ total: 7 })
  })

  it('normalizes an API error envelope with request ID', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: false, error: { code: 'TICKET_NOT_FOUND', message: 'Ticket not found.' }, request_id: 'req-404' }), { status: 404, headers: { 'Content-Type': 'application/json' } })))
    const caught = await apiRequest('/missing').catch((error: unknown) => error)
    expect(caught).toBeInstanceOf(ApiClientError)
    expect(caught).toMatchObject({ code: 'TICKET_NOT_FOUND', status: 404, requestId: 'req-404' })
  })
})
