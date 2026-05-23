<template>
  <div class="user-profile-container">
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6" v-for="stat in userStats" :key="stat.label">
        <div class="stat-card">
          <div class="label">{{ stat.label }}</div>
          <div class="value">{{ stat.value }}</div>
          <el-icon :class="['icon', stat.color]"><component :is="stat.icon" /></el-icon>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <div class="chart-card">
          <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">
            <span>动态主题演化追踪</span>
            <el-radio-group v-model="topicInterval" size="small" @change="loadTopicEvolution">
              <el-radio-button value="day">按日</el-radio-button>
              <el-radio-button value="week">按周</el-radio-button>
              <el-radio-button value="month">按月</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="topicEvolutionRef" style="height: 450px;"></div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="chart-card">
          <div class="card-header">活跃用户角色分布</div>
          <div ref="roleChartRef" style="height: 450px;"></div>
        </div>
      </el-col>
    </el-row>

    <div class="chart-card" style="margin-top: 20px">
      <div class="card-header">影响力用户排行</div>
      <el-table :data="userList" stripe style="width: 100%">
        <el-table-column prop="user_id" label="用户" width="150">
          <template #default="scope">
            {{ scope.row.nickname || scope.row.user_id }}
          </template>
        </el-table-column>
        <el-table-column prop="fans_count" label="粉丝数" sortable width="100" />
        <el-table-column prop="activity_score" label="活跃度" sortable width="140">
          <template #default="scope">
            <el-progress
              :percentage="Math.min(scope.row.activity_score ?? 0, 100)"
              :format="() => (scope.row.activity_score ?? 0).toFixed(0)"
              :color="activityColor(scope.row.activity_score)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="influence_score" label="影响力得分" sortable width="140">
          <template #default="scope">
            <el-progress
              :percentage="Math.min((scope.row.influence_score ?? 0) * 100, 100)"
              :format="() => (scope.row.influence_score ?? 0).toFixed(3)"
              status="warning"
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
        <el-table-column label="兴趣主题" width="160">
          <template #default="scope">
            <el-tag
              v-for="topic in (scope.row.top_topics || []).slice(0, 2)"
              :key="topic"
              type="info"
              size="small"
              style="margin-right: 4px; margin-bottom: 2px;"
            >{{ topic }}</el-tag>
            <span v-if="!scope.row.top_topics || scope.row.top_topics.length === 0" style="color:#ccc;font-size:12px">—</span>
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

const topicEvolutionRef = ref(null)
const roleChartRef = ref(null)
const userList = ref([])
const topicInterval = ref('week')
const userStats = ref([
  { label: '平均PageRank', value: '-', icon: 'Star', color: 'blue' },
  { label: '网络密度', value: '-', icon: 'Share', color: 'green' },
  { label: '核心节点数', value: '-', icon: 'UserFilled', color: 'orange' },
  { label: '传播层级', value: '-', icon: 'Histogram', color: 'purple' }
])

let topicEvolutionChart = null
let roleChart = null

const getRoleTagType = (role) => {
  const typeMap = {
    '核心传播者': 'danger',
    '意见领袖': 'warning',
    '活跃参与者': 'success',
    '潜力用户': 'primary',
    '普通用户': 'info'
  }
  return typeMap[role] || 'info'
}

const getSentimentTagType = (tendency) => {
  if (tendency === '积极') return 'success'
  if (tendency === '消极') return 'danger'
  return 'info'
}

const activityColor = (score) => {
  const v = score ?? 0
  if (v >= 70) return '#67C23A'
  if (v >= 40) return '#E6A23C'
  return '#909399'
}

const loadTopicEvolution = async () => {
  if (!topicEvolutionChart) return
  try {
    const res = await request.get(`/api/topic/evolution?interval=${topicInterval.value}&top_n=6`)
    if (res.data.code !== 200) return
    const { series, legend } = res.data.data
    if (!series || series.length === 0) {
      topicEvolutionChart.setOption({
        title: { text: '暂无话题时序数据', left: 'center', top: 'middle', textStyle: { color: '#ccc', fontSize: 14 } }
      })
      return
    }
    topicEvolutionChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: legend, top: 10, type: 'scroll' },
      singleAxis: [{
        type: 'time',
        axisLabel: { formatter: (val) => new Date(val).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) },
        top: '15%',
        height: '75%',
        axisLine: { lineStyle: { color: '#ccc' } }
      }],
      series: [{
        type: 'themeRiver',
        emphasis: { itemStyle: { shadowBlur: 20, shadowColor: 'rgba(0,0,0,0.2)' } },
        label: { show: true, margin: 4 },
        data: series
      }]
    }, true)
  } catch (e) {
    console.error('加载主题演化数据失败:', e)
  }
}

const loadData = async () => {
  const apiBase = '/api/user'
  try {
    const [statsRes, listRes, roleRes] = await Promise.all([
      request.get(`${apiBase}/stats`),
      request.get(`${apiBase}/list?page_size=10`),
      request.get(`${apiBase}/role-distribution`)
    ])

    if (statsRes.data.code === 200) {
      const stats = statsRes.data.data
      userStats.value = [
        { label: '平均PageRank', value: stats.avg_pagerank, icon: 'Star', color: 'blue' },
        { label: '网络密度', value: stats.network_density, icon: 'Share', color: 'green' },
        { label: '核心节点数', value: stats.core_nodes, icon: 'UserFilled', color: 'orange' },
        { label: '传播层级', value: stats.propagation_levels, icon: 'Histogram', color: 'purple' }
      ]
    }

    userList.value = listRes.data.data?.users || []

    if (roleRes.data.code === 200 && roleRes.data.data.length > 0 && roleChart) {
      roleChart.setOption({
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left' },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
          label: { show: true, formatter: '{b}: {c} ({d}%)' },
          data: roleRes.data.data
        }]
      })
    }

    await loadTopicEvolution()
  } catch (error) {
    console.error('加载用户数据失败:', error)
  }
}

watch([globalDateRange, globalSearch], () => {
  loadData()
}, { deep: true })

const handleResize = () => {
  topicEvolutionChart?.resize()
  roleChart?.resize()
}

onMounted(() => {
  topicEvolutionChart = echarts.init(topicEvolutionRef.value)
  roleChart = echarts.init(roleChartRef.value)
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  topicEvolutionChart?.dispose()
  roleChart?.dispose()
})
</script>

<style scoped>
.stat-card {
  background: #fff; padding: 20px; border-radius: 8px; position: relative;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}
.stat-card .label { color: #909399; font-size: 14px; }
.stat-card .value { font-size: 24px; font-weight: bold; margin-top: 5px; }
.stat-card .icon { position: absolute; right: 20px; top: 50%; transform: translateY(-50%); font-size: 40px; opacity: 0.15; }

.chart-card { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
.card-header { font-weight: bold; margin-bottom: 15px; border-left: 4px solid #67C23A; padding-left: 10px; }

.blue { color: #409EFF; }
.green { color: #67C23A; }
.orange { color: #E6A23C; }
.purple { color: #9b59b6; }
</style>
