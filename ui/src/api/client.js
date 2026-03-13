import axios from 'axios'

const http = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
})

export const engine = {
  start: () => http.post('/engine/start'),
  stop: () => http.post('/engine/stop'),
  pause: () => http.post('/engine/pause'),
  resume: () => http.post('/engine/resume'),
  status: () => http.get('/engine/status'),
  resetCircuitBreaker: () => http.post('/engine/reset-circuit-breaker'),
}

export const config = {
  getTopics: () => http.get('/topics'),
  updateTopics: (topics) => http.post('/topics', topics),
  getSettings: () => http.get('/settings'),
  updateSettings: (settings) => http.put('/settings', settings),
  getPrompts: () => http.get('/prompts'),
  getPrompt: (name) => http.get(`/prompts/${name}`),
  updatePrompt: (name, text) => http.put(`/prompts/${name}`, { text }),
  resetPrompt: (name) => http.get(`/prompts/${name}/default`),
  testPrompt: (prompt_name, variables) =>
    http.post('/prompts/test', { prompt_name, variables }),
}

export const analytics = {
  daily: () => http.get('/analytics/daily'),
  weekly: () => http.get('/analytics/weekly'),
  topTopics: () => http.get('/analytics/top-topics'),
  summary: () => http.get('/analytics/summary'),
  campaignFunnel: () => http.get('/analytics/campaign-funnel'),
  recentActivity: (limit = 50) => http.get('/analytics/recent-activity', { params: { limit } }),
  skippedPosts: (limit = 50) => http.get('/analytics/skipped-posts', { params: { limit } }),
  actedPosts: (limit = 50) => http.get('/analytics/acted-posts', { params: { limit } }),
  commentHistory: (limit = 50) => http.get('/analytics/comment-history', { params: { limit } }),
}

export const campaigns = {
  list: () => http.get('/campaigns'),
  create: (data) => http.post('/campaigns', data),
  update: (id, data) => http.put(`/campaigns/${id}`, data),
  delete: (id) => http.delete(`/campaigns/${id}`),
  enroll: (id, lead_ids) => http.post(`/campaigns/${id}/enroll`, { lead_ids }),
  stats: (id) => http.get(`/campaigns/${id}/stats`),
}

export const leads = {
  list: (params) => http.get('/leads', { params }),
  get: (id) => http.get(`/leads/${id}`),
  enrich: (id) => http.post(`/leads/${id}/enrich`),
  enrichAll: () => http.post('/leads/enrich-all'),
  export: () => http.get('/leads/export', { responseType: 'blob' }),
}

export const content = {
  getQueue: () => http.get('/content/queue'),
  schedule: (data) => http.post('/content/schedule', data),
  cancel: (id) => http.delete(`/content/queue/${id}`),
  publishNow: (data) => http.post('/content/publish-now', data),
}

export default http
