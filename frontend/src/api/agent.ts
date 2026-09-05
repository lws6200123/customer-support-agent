import { apiRequest } from './client'
import type { AgentRunDetail, AgentStep, TraceSteps } from './types'

export function getAgentRun(runId: number): Promise<AgentRunDetail> { return apiRequest(`/api/v1/agent-runs/${runId}`) }
export async function getAgentSteps(runId: number): Promise<AgentStep[]> {
  return (await apiRequest<TraceSteps>(`/api/v1/agent-runs/${runId}/steps`)).items
}
