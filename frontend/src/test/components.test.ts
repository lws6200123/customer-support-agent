import { mount } from '@vue/test-utils'
import Antd from 'ant-design-vue'
import { describe, expect, it } from 'vitest'
import DecisionTag from '../components/DecisionTag.vue'
import AgentTimeline from '../components/AgentTimeline.vue'
import type { AgentStep } from '../api/types'

describe('shared presentation', () => {
  it('maps decisions to non-financial wording', () => {
    const wrapper = mount(DecisionTag, { props: { decision: 'AUTO_RESOLVE' }, global: { plugins: [Antd] } })
    expect(wrapper.text()).toBe('自动处理')
    expect(wrapper.text()).not.toContain('退款完成')
  })
  it('orders Agent timeline steps by sequence', () => {
    const steps: AgentStep[] = [2, 1].map((sequence) => ({ sequence, node: `node-${sequence}`, action: null, tool: null, status: 'SUCCESS', latency_ms: sequence, input_summary: null, output_summary: `summary-${sequence}`, error_code: null, created_at: '2026-09-05T00:00:00' }))
    const wrapper = mount(AgentTimeline, { props: { steps }, global: { plugins: [Antd] } })
    expect(wrapper.text().indexOf('node-1')).toBeLessThan(wrapper.text().indexOf('node-2'))
  })
})
