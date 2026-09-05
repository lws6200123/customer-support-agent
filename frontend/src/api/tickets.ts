import { apiRequest } from './client'
import type { Decision, Intent, TicketDetail, TicketListResponse, TicketStatus } from './types'

export interface TicketFilters { page: number; pageSize: number; status?: TicketStatus; decision?: Decision; intent?: Intent }

export function listTickets(filters: TicketFilters): Promise<TicketListResponse> {
  const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
  if (filters.status) params.set('status', filters.status)
  if (filters.decision) params.set('decision', filters.decision)
  if (filters.intent) params.set('intent', filters.intent)
  return apiRequest(`/api/v1/tickets?${params}`)
}

export function getTicket(ticketId: string): Promise<TicketDetail> {
  return apiRequest(`/api/v1/tickets/${encodeURIComponent(ticketId)}`)
}
