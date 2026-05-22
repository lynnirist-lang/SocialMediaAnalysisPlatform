import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '../api/request'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const username = ref(localStorage.getItem('username') || '')

  const isLoggedIn = computed(() => !!token.value)

  async function login(loginForm) {
    const res = await request.post('/api/auth/login', loginForm)
    const data = res.data?.data
    if (!data?.access_token) {
      throw new Error(res.data?.message || '登录失败')
    }
    token.value = data.access_token
    username.value = data.username
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('username', data.username)
    return data
  }

  async function register(registerForm) {
    const res = await request.post('/api/auth/register', registerForm)
    return res.data
  }

  async function fetchMe() {
    const res = await request.get('/api/auth/me')
    if (res.data?.data?.username) {
      username.value = res.data.data.username
      localStorage.setItem('username', res.data.data.username)
    }
    return res.data?.data
  }

  function logout() {
    token.value = ''
    username.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
  }

  return { token, username, isLoggedIn, login, register, fetchMe, logout }
})
