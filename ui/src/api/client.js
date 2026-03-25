import axios from 'axios'

const http = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
})

// Attach API token to every request from localStorage
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('api_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// Bootstrap: fetch token from server on first load if not stored
async function _bootstrapToken() {
  if (localStorage.getItem('api_token')) return
  try {
    const res = await axios.get('http://localhost:8000/auth/token')
    if (res.data?.token) {
      localStorage.setItem('api_token', res.data.token)
    }
  } catch { /* server may not be up yet */ }
}

// Track in-flight bootstrap to avoid parallel fetches
let _bootstrapPromise = null
function _ensureToken() {
  if (localStorage.getItem('api_token')) return Promise.resolve()
  if (!_bootstrapPromise) {
    _bootstrapPromise = _bootstrapToken().finally(() => { _bootstrapPromise = null })
  }
  return _bootstrapPromise
}

_ensureToken()

// On 401: re-fetch token once and retry the original request
http.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status === 401 && !original._retried) {
      original._retried = true
      localStorage.removeItem('api_token')
      await _bootstrapToken()
      const token = localStorage.getItem('api_token')
      if (token) {
        original.headers['Authorization'] = `Bearer ${token}`
        return http(original)
      }
    }
    return Promise.reject(err)
  }
)

export const engine = {
  start: () => http.post('/engine/start'),
  stop: () => http.post('/engine/stop'),
  pause: () => http.post('/engine/pause'),
  resume: () => http.post('/engine/resume'),
  status: () => http.get('/engine/status'),
  resetCircuitBreaker: () => http.post('/engine/reset-circuit-breaker'),
  scanNow: () => http.post('/engine/scan-now'),
  pendingPreviews: () => http.get('/engine/pending-previews'),
  approveComment: (post_id, comment_text) => http.post('/engine/approve-comment', { post_id, comment_text }),
  rejectComment: (post_id) => http.post('/engine/reject-comment', { post_id }),
  runCommentMonitor: () => http.post('/engine/run-comment-monitor'),
}

export const config = {
  getTopics: () => http.get('/topics'),
  updateTopics: (topics) => http.post('/topics', topics),
  getAllTopics: () => http.get('/topics/all'),
  topicPerformance: () => http.get('/topics/performance'),
  activateTopic: (name) => http.post(`/topics/${encodeURIComponent(name)}/activate`),
  deactivateTopic: (name) => http.post(`/topics/${encodeURIComponent(name)}/deactivate`),
  hashtagSuggestions: (name) => http.get(`/topics/${encodeURIComponent(name)}/hashtags`),
  runIteration: () => http.post('/topics/run-cycle'),
  getSettings: () => http.get('/settings'),
  updateSettings: (settings) => http.put('/settings', settings),
  getPrompts: () => http.get('/prompts'),
  getPrompt: (name) => http.get(`/prompts/${name}`),
  updatePrompt: (name, text) => http.put(`/prompts/${name}`, { text }),
  resetPrompt: (name) => http.get(`/prompts/${name}/default`),
  testPrompt: (prompt_name, variables) =>
    http.post('/prompts/test', { prompt_name, variables }, { timeout: 120000 }),
  setupStatus: () => http.get('/setup/status'),
  getGroqKeyStatus: () => http.get('/api-keys/groq'),
  saveGroqKey: (api_key) => http.post('/api-keys/groq', { api_key }),
  getOpenRouterKeyStatus: () => http.get('/api-keys/openrouter'),
  saveOpenRouterKey: (api_key) => http.post('/api-keys/openrouter', { api_key }),
  getLinkedInStatus: () => http.get('/credentials/linkedin'),
  saveLinkedInCredentials: (email, password) => http.post('/credentials/linkedin', { email, password }),
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
  generateStructured: (data) => http.post('/content/generate-structured', data, { timeout: 120000 }),
  generateV2: (data) => http.post('/content/generate-v2', data, { timeout: 300000 }),
  ideaPool: (params) => http.get('/content/idea-pool', { params }),
  synthesizeBrief: (selections) =>
    http.post('/content/synthesize-brief', { selections }, { timeout: 60000 }),
  generateFromBrief: (data) =>
    http.post('/content/generate-from-brief', data, { timeout: 120000 }),
}

export const intelligence = {
  insights: (params) => http.get('/intelligence/insights', { params }),
  patterns: (params) => http.get('/intelligence/patterns', { params }),
  patternsForGeneration: (topic) =>
    http.get('/intelligence/patterns/for-generation', { params: { topic } }),
  extract: () => http.post('/intelligence/extract', null, { timeout: 120000 }),
  extractText: (text, source = 'MANUAL') =>
    http.post('/intelligence/extract-text', { text, source }, { timeout: 60000 }),
  logSession: (data) => http.post('/intelligence/session', data),
  preferences: () => http.get('/intelligence/preferences'),
  status: () => http.get('/intelligence/status'),
  patternDetail: (id) => http.get(`/intelligence/patterns/${id}`),
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
  clearData: () => http.post('/server/clear-data'),
}

export default http
