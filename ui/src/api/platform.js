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
  users: () => platform.get('/platform/admin/users'),
  user: (id) => platform.get(`/platform/admin/users/${id}`),
  suspend: (id) => platform.post(`/platform/admin/users/${id}/suspend`),
  unsuspend: (id) => platform.post(`/platform/admin/users/${id}/unsuspend`),
  deleteUser: (id) => platform.delete(`/platform/admin/users/${id}`),
  containers: () => platform.get('/platform/admin/containers'),
  restartContainer: (id) => platform.post(`/platform/admin/containers/${id}/restart`),
  system: () => platform.get('/platform/admin/system'),
}

export default platform
