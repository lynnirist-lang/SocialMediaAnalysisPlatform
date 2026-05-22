<template>
  <el-container class="app-container">
    <el-aside width="240px" class="sidebar">
      <div class="logo">社交媒体分析平台</div>
      <el-menu
        :default-active="activeMenu"
        background-color="#2c3e50"
        text-color="#fff"
        active-text-color="#409EFF"
        @select="handleMenuSelect"
      >
        <el-menu-item index="dashboard">
          <el-icon><DataLine /></el-icon>
          <span>数据看板</span>
        </el-menu-item>
        <el-menu-item index="sentiment">
          <el-icon><PieChart /></el-icon>
          <span>情感分析</span>
        </el-menu-item>
        <el-menu-item index="topic">
          <el-icon><Connection /></el-icon>
          <span>主题洞察</span>
        </el-menu-item>
        <el-menu-item index="user">
          <el-icon><User /></el-icon>
          <span>用户画像</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="main-wrapper">
      <el-header class="header">
        <div class="header-left">
          <span class="page-title">{{ pageTitle }}</span>
        </div>

        <div class="header-right">
          <span class="user-label">{{ auth.username }}</span>
          <el-date-picker
            v-model="globalDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            size="default"
            style="width: 240px"
          />
          <el-input
            v-model="globalSearch"
            placeholder="话题搜索..."
            prefix-icon="Search"
            style="width: 180px; margin-left: 12px;"
          />
          <el-button type="primary" style="margin-left: 12px" @click="handleExportReport">导出报告</el-button>
          <el-button style="margin-left: 8px" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="main-content">
        <transition name="fade-transform" mode="out-in">
          <component :is="currentComponent" />
        </transition>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, provide, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataLine, PieChart, Connection, User } from '@element-plus/icons-vue'
import Dashboard from '../components/Dashboard.vue'
import Sentiment from '../components/Sentiment.vue'
import Topic from '../components/Topic.vue'
import UserProfile from '../components/UserProfile.vue'
import { useAuthStore } from '../stores/auth'
import request from '../api/request'

const router = useRouter()
const auth = useAuthStore()
const activeMenu = ref('dashboard')
const globalDateRange = ref([])
const globalSearch = ref('')

provide('globalDateRange', globalDateRange)
provide('globalSearch', globalSearch)

const currentComponent = computed(() => {
  const components = { dashboard: Dashboard, sentiment: Sentiment, topic: Topic, user: UserProfile }
  return components[activeMenu.value]
})

const pageTitle = computed(() => {
  const titles = { dashboard: '数据看板', sentiment: '情感分析', topic: '主题洞察', user: '用户画像' }
  return titles[activeMenu.value]
})

const handleMenuSelect = (index) => { activeMenu.value = index }

onMounted(async () => {
  try {
    await auth.fetchMe()
  } catch {
    auth.logout()
    router.push('/login')
  }
})

const handleLogout = () => {
  auth.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

const formatDateForApi = (date) => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const formatDateForFilename = () => {
  const now = new Date()
  return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`
}

const isPdfBlob = async (blob) => {
  const header = await blob.slice(0, 5).arrayBuffer()
  const bytes = new Uint8Array(header)
  return bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46
}

const handleExportReport = async () => {
  try {
    const response = await request.post(
      '/api/export/report',
      {
        date_range: globalDateRange.value?.map((d) => formatDateForApi(d)) || [],
        search_keyword: globalSearch.value,
      },
      { responseType: 'blob', timeout: 120000 }
    )

    let blob = response.data instanceof Blob
      ? response.data
      : new Blob([response.data], { type: 'application/pdf' })

    if (!(await isPdfBlob(blob))) {
      const text = await blob.text()
      try {
        const err = JSON.parse(text)
        ElMessage.error(err.detail || err.message || '导出失败')
      } catch {
        ElMessage.error('导出失败：服务器未返回有效 PDF')
      }
      return
    }

    blob = new Blob([await blob.arrayBuffer()], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `weibo_report_${formatDateForFilename()}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    ElMessage.success('报告导出成功')
  } catch (error) {
    console.error('导出错误:', error)
    if (!error?.response) {
      ElMessage.error('导出失败，请确认后端服务已启动')
    }
  }
}
</script>

<style scoped>
.app-container { height: 100vh; background-color: #f0f2f5; }
.sidebar { background-color: #2c3e50; transition: width 0.3s; }
.logo { height: 60px; line-height: 60px; text-align: center; color: #409EFF; font-weight: bold; font-size: 18px; background: #1e2b37; }
.header {
  background: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 64px;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
}
.page-title { font-size: 18px; font-weight: 600; color: #333; }
.header-right { display: flex; align-items: center; }
.user-label { margin-right: 12px; color: #606266; font-size: 14px; }
.main-content { padding: 20px; }
.fade-transform-enter-active, .fade-transform-leave-active { transition: all .3s; }
.fade-transform-enter-from { opacity: 0; transform: translateX(-10px); }
.fade-transform-leave-to { opacity: 0; transform: translateX(10px); }
</style>
