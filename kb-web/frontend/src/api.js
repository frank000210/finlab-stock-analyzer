import axios from 'axios'
import { isPublicMode } from './authMode'

const client = axios.create({ baseURL: '/api' })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('kb_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !(await isPublicMode())) {
      localStorage.removeItem('kb_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
