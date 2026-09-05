import { flushPromises, mount } from '@vue/test-utils'
import Antd from 'ant-design-vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TicketsPage from '../pages/TicketsPage.vue'
import { listTickets } from '../api/tickets'
import { submitHumanReview } from '../api/reviews'

vi.mock('../api/tickets', () => ({ listTickets: vi.fn() }))

afterEach(() => vi.unstubAllGlobals())

describe('tickets and reviews', () => {
  it('renders API ticket rows', async () => {
    vi.mocked(listTickets).mockResolvedValue({ page: 1, page_size: 20, total: 1, items: [{ ticket_id: 'TKT-DEMO-1', customer_id: 'CUST-1', order_id: 'ORD-1', category: 'DELIVERY', status: 'under_review', decision: 'ESCALATE_TO_HUMAN', priority: 'high', subject: 'Package is late', created_at: '2026-09-05T00:00:00', updated_at: '2026-09-05T00:00:00' }] })
    const wrapper = mount(TicketsPage, { global: { plugins: [Antd], stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()
    expect(wrapper.text()).toContain('TKT-DEMO-1')
    expect(wrapper.text()).toContain('需要人工审核')
  })
  it('sends a controlled human review action request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, data: { review_id: 3, ticket_id: 'TKT-1', action: 'RESOLVE', ticket_status: 'resolved', created_at: '2026-09-05T00:00:00' }, request_id: 'review-1' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    await submitHumanReview('TKT-1', 'RESOLVE', 'Reviewed safely')
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/human-reviews/TKT-1'), expect.objectContaining({ method: 'POST', body: JSON.stringify({ action: 'RESOLVE', review_note: 'Reviewed safely' }) }))
  })
})
