import { describe, expect, it } from 'vitest'
import {
  displayDecision,
  displayIntent,
  displayOrderStatus,
  displayTicketStatus,
  formatBrl,
} from '../utils/display'

describe('Chinese display mappings', () => {
  it('maps intents without changing API values', () => {
    expect(displayIntent('RETURN_REFUND')).toBe('退款/退货')
    expect(displayIntent('DELIVERY')).toBe('物流配送')
  })

  it('maps decisions to safe operational wording', () => {
    expect(displayDecision('AUTO_RESOLVE')).toBe('自动处理')
    expect(displayDecision('NEED_MORE_INFO')).toBe('待补充信息')
    expect(displayDecision('ESCALATE_TO_HUMAN')).toBe('需要人工审核')
    expect(displayDecision('AUTO_RESOLVE')).not.toContain('退款完成')
  })

  it('maps ticket and Olist order statuses', () => {
    expect(displayTicketStatus('awaiting_customer')).toBe('等待客户补充')
    expect(displayOrderStatus('delivered')).toBe('已送达')
  })

  it('falls back to the original value for unknown enums', () => {
    expect(displayTicketStatus('future_status')).toBe('future_status')
    expect(displayOrderStatus('future_order_status')).toBe('future_order_status')
  })

  it('formats canonical transaction amounts in BRL', () => {
    expect(formatBrl(299, 'BRL')).toBe('299.00 BRL')
    expect(formatBrl(299, 'BRL')).not.toMatch(/[¥￥]|CNY/)
  })
})
