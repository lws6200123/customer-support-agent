import { mount } from '@vue/test-utils'
import Antd from 'ant-design-vue'
import { describe, expect, it } from 'vitest'
import AgentDemoPage from '../pages/AgentDemoPage.vue'

describe('Agent demo form', () => {
  it('prevents an empty message submission', async () => {
    const wrapper = mount(AgentDemoPage, { global: { plugins: [Antd] } })
    await wrapper.find('form').trigger('submit')
    expect(wrapper.text()).toContain('请输入客户问题后再运行 Agent。')
  })
})
