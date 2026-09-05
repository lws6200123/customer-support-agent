import { apiRequest } from './client'
import type { HumanReviewAction, HumanReviewItem, HumanReviewResult, Page } from './types'

export function listHumanReviews(page = 1, pageSize = 20): Promise<Page<HumanReviewItem>> {
  return apiRequest(`/api/v1/human-reviews?page=${page}&page_size=${pageSize}`)
}
export function submitHumanReview(ticketId: string, action: HumanReviewAction, reviewNote?: string): Promise<HumanReviewResult> {
  return apiRequest(`/api/v1/human-reviews/${encodeURIComponent(ticketId)}`, {
    method: 'POST', body: JSON.stringify({ action, review_note: reviewNote || null }),
  })
}
