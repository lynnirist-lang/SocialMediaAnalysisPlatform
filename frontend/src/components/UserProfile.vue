<template>
  <div class="user-profile-container">
    <!-- 统计卡片行 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6" v-for="stat in userStats" :key="stat.label">
        <div class="stat-card" :style="{ borderTopColor: stat.accent }">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value">{{ stat.value }}</div>
          <el-icon class="stat-icon" :style="{ color: stat.accent }"><component :is="stat.icon" /></el-icon>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 左：用户关系网络图 -->
      <el-col :span="16">
        <div class="up-card">
          <div class="card-header">
            <span>用户影响力关系网络</span>
            <el-tag size="small" type="info" style="font-weight:normal;margin-left:8px;">Top 50 用户</el-tag>
          </div>
          <div v-if="networkEmpty" style="display:flex;justify-content:center;align-items:center;height:450px;">
            <el-empty description="暂无用户网络数据" :image-size="80" />
          </div>
          <div v-show="!networkEmpty" ref="networkChartRef" style="height:450px;"></div>
        </div>
      </el-col>

      <!-- 右：角色分布饼图 -->
      <el-col :span="8">
        <div class="up-card">
          <div class="card-header">活跃用户角色分布</div>
          <div ref="roleChartRef" style="height:450px;"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 影响力用户表 -->
    <div class="up-card" style="margin-top: 20px;">
      <div class="card-header">影响力用户排行</div>
      <el-table :data="userList" stripe style="width:100%">
        <el-table-column prop="user_id" label="用户" width="150">
          <template #default="scope">
            {{ scope.row.nickname || scope.row.user_id }}
          </template>
        </el-table-column>
        <el-table-column prop="fans_count" label="粉丝数" sortable width="100" />
        <el-table-column prop="activity_score" label="活跃度" sortable width="150">
          <template #default="scope">
            <el-progress
              :percentage="Math.min(scope.row.activity_score ?? 0, 100)"
              :format="() => (scope.row.activity_score ?? 0).toFixed(0)"
              :color="activityColor(scope.row.activity_score)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="influence_score" label="影响力" sortable width="150">
          <template #default="scope">
            <el-progress
              :percentage="Math.min((scope.row.influence_score ?? 0) * 100, 100)"
              :format="() => (scope.row.influence_score ?? 0).toFixed(3)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="sentiment_tendency" label="情感倾向" width="90">
          <template #default="scope">
            <el-tag :type="getSentimentTagType(scope.row.sentiment_tendency)" size="small">
              {{ scope.row.sentiment_tendency || '中性' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="兴趣主题" width="180">
          <template #default="scope">
            <el-tag
              v-for="topic in (scope.row.top_topics || []).slice(0, 2)"
              :key="topic"
              type="info"
              size="small"
              style="margin-right:4px;margin-bottom:2px;"
            >{{ topic }}</el-tag>
            <span v-if="!scope.row.top_topics || scope.row.top_topics.length === 0" style="color:#ccc;font-size:12px;">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="user_role" label="预测角色" width="110">
          <template #default="scope">
            <el-tag :type="getRoleTagType(scope.row.user_role)">{{ scope.row.user_role }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject, watch } from 'vue'
import * as echarts from 'echarts'
import request from '../api/request'

const globalDateRange = inject('globalDateRange')
const globalSearch = inject('globalSearch')

const networkChartRef = ref(null)
const roleChartRef = ref(null)
const userList = ref([])
const networkEmpty = ref(false)

const userStats = ref([
  { label: '平均PageRank', value: '-', icon: 'Star', accent: '#3b7dd8' },
  { label: '网络密度', value: '-', icon: 'Share', accent: '#10b981' },
  { label: '核心节点数', value: '-', icon: 'UserFilled', accent: '#f59e0b' },
  { label: '传播层级', value: '-', icon: 'Histogram', accent: '#8b5cf6' },
])

let networkChart = null
let roleChart = null

const ROLE_COLORS = {
  '核心传播者': '#ef4444',
  '意见领袖': '#f59e0b',
  '活跃参与者': '#10b981',
  '潜力用户': '#3b7dd8',
  '普通用户': '#94a3b8',
}
const ROLE_LIST = Object.keys(ROLE_COLORS)

// ── 用户网络图 ─────────────────────────────────────────────────────────────
const loadNetworkGraph = async () => {
  try {
    const res = await request.get('/api/user/network?top_n=50')
    if (res.data.code !== 200 || !res.data.data.nodes.length) {
      networkEmpty.value = true
      return
    }
    const { nodes, links } = res.data.data
    networkEmpty.value = false

    if (!networkChart && networkChartRef.value) {
      networkChart = echarts.init(networkChartRef.value)
    }
    if (!networkChart) return

    networkChart.setOption({
      tooltip: {
        formatter: p => p.dataType === 'node'
          ? `<b>${p.name}</b><br/>粉丝：${p.value?.toLocaleString() ?? 0}<br/>角色：${p.data.category}`
          : ''
      },
      legend: [{
        data: ROLE_LIST,
        bottom: 0,
        textStyle: { fontSize: 12, color: '#1a2a4a' },
      }],
      series: [{
        type: 'graph',
        layout: 'force',
        data: nodes.map(n => ({
          ...n,
          category: ROLE_LIST.indexOf(n.category) >= 0 ? ROLE_LIST.indexOf(n.category) : 4,
          itemStyle: { color: ROLE_COLORS[n.category] ?? '#94a3b8' },
        })),
        links,
        categories: ROLE_LIST.map(k => ({ name: k, itemStyle: { color: ROLE_COLORS[k] } })),
        roam: true,
        label: { show: true, position: 'right', fontSize: 10, color: '#334' },
        force: { repulsion: 80, edgeLength: [30, 70], gravity: 0.08 },
        lineStyle: { color: '#dde4ef', width: 0.8, opacity: 0.6 },
        emphasis: { focus: 'adjacency' },
      }]
    })
  } catch (e) {
    networkEmpty.value = true
    console.error('网络图加载失败:', e)
  }
}

// ── 主数据加载 ─────────────────────────────────────────────────────────────
const loadData = async () => {
  try {
    const [statsRes, listRes, roleRes] = await Promise.all([
      request.get('/api/user/stats'),
      request.get('/api/user/list?page_size=10'),
      request.get('/api/user/role-distribution'),
    ])

    if (statsRes.data.code === 200) {
      const s = statsRes.data.data
      userStats.value = [
        { label: '平均PageRank', value: s.avg_pagerank, icon: 'Star', accent: '#3b7dd8' },
        { label: '网络密度', value: s.network_density, icon: 'Share', accent: '#10b981' },
        { label: '核心节点数', value: s.core_nodes, icon: 'UserFilled', accent: '#f59e0b' },
        { label: '传播层级', value: s.propagation_levels, icon: 'Histogram', accent: '#8b5cf6' },
      ]
    }

    userList.value = listRes.data.data?.users || []

    if (roleRes.data.code === 200 && roleRes.data.data.length > 0 && roleChart) {
      const palette = Object.values(ROLE_COLORS)
      roleChart.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'horizontal', bottom: 0, left: 'center', textStyle: { fontSize: 12 } },
        color: palette,
        series: [{
          type: 'pie',
          radius: ['38%', '62%'],
          center: ['50%', '44%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: true, formatter: '{b}\n{d}%', lineHeight: 18, fontSize: 12 },
          labelLine: { length: 12, length2: 8, smooth: true },
          data: roleRes.data.data,
        }]
      })
    }
  } catch (e) {
    console.error('加载用户数据失败:', e)
  }
}

const getRoleTagType = role => ({ '核心传播者': 'danger', '意见领袖': 'warning', '活跃参与者': 'success', '潜力用户': 'primary' }[role] ?? 'info')
const getSentimentTagType = t => t === '积极' ? 'success' : t === '消极' ? 'danger' : 'info'
const activityColor = score => (score ?? 0) >= 70 ? '#10b981' : (score ?? 0) >= 40 ? '#f59e0b' : '#94a3b8'

watch([globalDateRange, globalSearch], () => loadData(), { deep: true })

const handleResize = () => {
  networkChart?.resize()
  roleChart?.resize()
}

onMounted(async () => {
  roleChart = echarts.init(roleChartRef.value)
  await Promise.all([loadData(), loadNetworkGraph()])
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  networkChart?.dispose()
  roleChart?.dispose()
})
</script>

<style scoped>
.user-profile-container { padding: 4px; }

.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 8px rgba(0, 30, 70, 0.08);
  border-top: 4px solid transparent;
  position: relative;
  overflow: hidden;
}

.stat-label { font-size: 13px; color: #6b7a8d; margin-bottom: 6px; }
.stat-value { font-size: 26px; font-weight: 700; color: #1a2a4a; }
.stat-icon { font-size: 44px; opacity: 0.12; }

.up-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 1px 8px rgba(0, 30, 70, 0.08);
}

.card-header {
  font-size: 15px;
  font-weight: 600;
  color: #1a2a4a;
  margin-bottom: 16px;
  padding-left: 10px;
  border-left: 4px solid #10b981;
  display: flex;
  align-items: center;
}
</style>
