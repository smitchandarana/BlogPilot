import axios from 'axios'

const PLATFORM_URL = import.meta.env.VITE_PLATFORM_URL || 'http://localhost:9000'

const platform = axios.create({
  baseURL: PLATFORM_URL,
  timeout: 30000,
})

// Attach platform JWT to every request
platform.interceptors.request.use((config) => {
  const token = localStorage.getItem('platform_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// On 401: clear stored token and dispatch event so AuthContext can log out
platform.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('platform_token')
      window.dispatchEvent(new CustomEvent('platform:unauthorized'))
    }
    return Promise.reject(err)
  }
)

export const auth = {
  signup: (email, password, name) =>
    platform.post('/platform/auth/signup', { email, password, name }),
  login: (email, password) =>
    platform.post('/platform/auth/login', { email, password }),
  me: () => platform.get('/platform/auth/me'),
  refresh: () => platform.post('/platform/auth/refresh'),
  forgotPassword: (email) =>
    platform.post('/platform/auth/forgot-password', { email }),
  resetPassword: (token, new_password) =>
    platform.post('/platform/auth/reset-password', { token, new_password }),
  changePassword: (current_password, new_password) =>
    platform.post('/platform/auth/change-password', { current_password, new_password }),
  changeEmail: (password, new_email) =>
    platform.post('/platform/auth/change-email', { password, new_email }),
  deleteAccount: () => platform.delete('/platform/auth/account'),
}

export const containers = {
  provision: () => platform.post('/platform/containers/provision'),
  start: () => platform.post('/platform/containers/start'),
  stop: () => platform.post('/platform/containers/stop'),
  restart: () => platform.post('/platform/containers/restart'),
  destroy: (deleteData = false) =>
    platform.delete(`/platform/containers?delete_data=${deleteData}`),
  reset: () => platform.post('/platform/containers/reset'),
  status: () => platform.get('/platform/containers/status'),
}

export const billing = {
  createCheckout: () => platform.post('/platform/billing/create-checkout'),
  subscription: () => platform.get('/platform/billing/subscription'),
  cancel: () => platform.post('/platform/billing/cancel'),
}

export const admin = {
  // Existing
  users: () => platform.get('/platform/admin/users'),
  user: (id) => platform.get(`/platform/admin/users/${id}`),
  suspend: (id) => platform.post(`/platform/admin/users/${id}/suspend`),
  unsuspend: (id) => platform.post(`/platform/admin/users/${id}/unsuspend`),
  deleteUser: (id) => platform.delete(`/platform/admin/users/${id}`),
  containers: () => platform.get('/platform/admin/containers'),
  restartContainer: (id) => platform.post(`/platform/admin/containers/${id}/restart`),
  system: () => platform.get('/platform/admin/system'),

  // New
  createUser: (data) => platform.post('/platform/admin/users', data),
  approveUser: (id) => platform.post(`/platform/admin/users/${id}/approve`),
  rejectUser: (id) => platform.post(`/platform/admin/users/${id}/reject`),
  pauseUser: (id) => platform.post(`/platform/admin/users/${id}/pause`),
  resumeUser: (id) => platform.post(`/platform/admin/users/${id}/resume`),
  provisionUser: (id) => platform.post(`/platform/admin/users/${id}/provision`),
  changeRole: (id, role) => platform.post(`/platform/admin/users/${id}/change-role`, { role }),
  auditLog: () => platform.get('/platform/admin/audit-log'),
  setLinkedInCredentials: (id, linkedin_email, linkedin_password) =>
    platform.post(`/platform/admin/users/${id}/linkedin-credentials`, { linkedin_email, linkedin_password }),
  clearLinkedInCredentials: (id) =>
    platform.delete(`/platform/admin/users/${id}/linkedin-credentials`),
}

export const platformHealth = {
  tailscale: () => platform.get('/platform/health/tailscale'),
  containers: () => platform.get('/platform/health/containers'),
}

export default platform
