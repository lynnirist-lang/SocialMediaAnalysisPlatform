import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '',   // 同源请求，由 Vite proxy 转发到 http://localhost:8080
  timeout: 60000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

const readBlobErrorMessage = async (data) => {
  if (!(data instanceof Blob)) {
    return null
  }
  try {
    const text = await data.text()
    const json = JSON.parse(text)
    return json.detail || json.message || null
  } catch {
    return null
  }
}

request.interceptors.response.use(
  async (response) => {
    if (response.config?.responseType === 'blob' && response.data instanceof Blob) {
      const contentType = response.headers['content-type'] || response.data.type || ''
      if (contentType.includes('application/json')) {
        const detail = await readBlobErrorMessage(response.data)
        return Promise.reject({
          response: { status: response.status, data: { detail: detail || '导出失败' } },
        })
      }
    }
    return response
  },
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('username')
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
    }
    let msg = error.response?.data?.detail || error.message || '请求失败'
    if (error.response?.data instanceof Blob) {
      const blobMsg = await readBlobErrorMessage(error.response.data)
      if (blobMsg) {
        msg = blobMsg
      }
    }
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(error)
  }
)

export default request
