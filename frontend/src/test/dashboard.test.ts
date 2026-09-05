import { flushPromises, mount } from '@vue/test-utils'
import Antd from 'ant-design-vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from '../pages/DashboardPage.vue'
import { getDashboardSummary } from '../api/dashboard'

vi.mock('../api/dashboard', () => ({ getDashboardSummary: vi.fn() }))
const mocked = vi.mocked(getDashboardSummary)
const base = { total_tickets: 0, tickets_by_status: [], runs_by_decision: [], auto_resolve_count: 0, need_more_info_count: 0, human_escalation_count: 0, average_agent_latency_ms: 0, recent_runs: [] }

describe('Dashboard', () => {
  beforeEach(() => mocked.mockReset())
  it('renders empty distributions safely', async () => {
    mocked.mockResolvedValue(base)
    const wrapper = mount(DashboardPage, { global: { plugins: [Antd], stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无 Agent 决策数据')
    expect(wrapper.text()).toContain('暂无工单数据')
  })
  it('renders real response values without invented percentages', async () => {
    mocked.mockResolvedValue({ ...base, total_tickets: 24, auto_resolve_count: 9, need_more_info_count: 4, human_escalation_count: 2, average_agent_latency_ms: 1234, tickets_by_status: [{ name: 'open', count: 3 }], runs_by_decision: [{ name: 'AUTO_RESOLVE', count: 9 }] })
    const wrapper = mount(DashboardPage, { global: { plugins: [Antd], stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()
    expect(wrapper.text()).toContain('24')
    expect(wrapper.text()).toContain('自动处理')
    expect(wrapper.text()).toContain('1.23 s')
  })
})
