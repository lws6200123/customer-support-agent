import { createRouter, createWebHistory } from 'vue-router'
import DashboardPage from '../pages/DashboardPage.vue'
import TicketsPage from '../pages/TicketsPage.vue'
import TicketDetailPage from '../pages/TicketDetailPage.vue'
import HumanReviewsPage from '../pages/HumanReviewsPage.vue'
import AgentDemoPage from '../pages/AgentDemoPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardPage },
    { path: '/tickets', name: 'tickets', component: TicketsPage },
    { path: '/tickets/:ticketId', name: 'ticket-detail', component: TicketDetailPage },
    { path: '/human-reviews', name: 'human-reviews', component: HumanReviewsPage },
    { path: '/demo', name: 'agent-demo', component: AgentDemoPage },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
