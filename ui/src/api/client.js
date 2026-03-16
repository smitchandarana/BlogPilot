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
  scanNow: () => http.post('/engine/scan-now'),
}

export const config = {
  getTopics: () => http.get('/topics'),
  updateTopics: (topics) => http.post('/topics', topics),
  getAllTopics: () => http.get('/topics/all'),
  topicPerformance: () => http.get('/topics/performance'),
  activateTopic: (name) => http.post(`/topics/${encodeURIComponent(name)}/activate`),
  deactivateTopic: (name) => http.post(`/topics/${encodeURIComponent(name)}/deactivate`),
  hashtagSuggestions: (name) => http.get(`/topics/${encodeURIComponent(name)}/hashtags`),
  getSettings: () => http.get('/settings'),
  updateSettings: (settings) => http.put('/settings', settings),
  getPrompts: () => http.get('/prompts'),
  getPrompt: (name) => http.get(`/prompts/${name}`),
  updatePrompt: (name, text) => http.put(`/prompts/${name}`, { text }),
  resetPrompt: (name) => http.get(`/prompts/${name}/default`),
  testPrompt: (prompt_name, variables) =>
    http.post('/prompts/test', { prompt_name, variables }),
  getGroqKeyStatus: () => http.get('/api-keys/groq'),
  saveGroqKey: (api_key) => http.post('/api-keys/groq', { api_key }),
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
  learningCommentQuality: () => http.get('/analytics/learning/comment-quality'),
  learningPostQuality: () => http.get('/analytics/learning/post-quality'),
  learningCalibration: () => http.get('/analytics/learning/scoring-calibration'),
  learningTiming: () => http.get('/analytics/learning/timing'),
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

export const research = {
  trigger: () => http.post('/research/trigger', null, { timeout: 180000 }),
  topics: (limit = 20) => http.get('/research/topics', { params: { limit } }),
  topicDetail: (id) => http.get(`/research/topics/${id}`),
  generateFromTopic: (id, opts) => http.post(`/research/topics/${id}/generate`, opts, { timeout: 60000 }),
  dismiss: (id) => http.delete(`/research/topics/${id}`),
  clearAll: () => http.delete('/research/topics'),
  status: () => http.get('/research/status'),
}

export const server = {
  restart: () => http.post('/server/restart'),
  shutdown: () => http.post('/server/shutdown'),
  info: () => http.get('/server/info'),
}

export default http
