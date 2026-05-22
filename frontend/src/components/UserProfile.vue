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
          <div class="card-header">用户传播网络</div>
          <div ref="networkChartRef" style="height: 450px;"></div>
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
         <el-table-column prop="user_id" label="用户ID" width="180">
          <template #default="scope">
            {{ scope.row.nickname || scope.row.user_id }}
          </template>
        </el-table-column>
        <el-table-column prop="fans_count" label="粉丝数" sortable />
        <el-table-column prop="pagerank_score" label="PageRank影响力" width="150">
          <template #default="scope">
            <el-progress :percentage="Math.min(scope.row.pagerank_score * 1000, 100)" :format="() => scope.row.pagerank_score.toFixed(4)" />
          </template>
        </el-table-column>
        <el-table-column prop="user_role" label="预测角色">
          <template #default="scope">
            <el-tag :type="getRoleTagType(scope.row.user_role)">{{ scope.row.user_role }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, inject, watch } from 'vue'
import * as echarts from 'echarts'
import request from '../api/request'
const globalDateRange = inject('globalDateRange')
const globalSearch = inject('globalSearch')

const networkChartRef = ref(null)
const roleChartRef = ref(null)
const userList = ref([])
const userStats = ref([
  { label: '平均PageRank', value: '-', icon: 'Star', color: 'blue' },
  { label: '网络密度', value: '-', icon: 'Share', color: 'green' },
  { label: '核心节点数', value: '-', icon: 'UserFilled', color: 'orange' },
  { label: '传播层级', value: '-', icon: 'Histogram', color: 'purple' }
])

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

// 监听变化并重新加载数据
watch([globalDateRange, globalSearch], ([newDates, newKeyword]) => {
  loadData(newDates, newKeyword)
}, { deep: true })

const loadData = (dateRange, keyword) => {
  const params = new URLSearchParams()

  if (dateRange && dateRange.length === 2) {
    params.append('start_date', dateRange[0].toISOString().split('T')[0])
    params.append('end_date', dateRange[1].toISOString().split('T')[0])
  }

  if (keyword) {
    params.append('keyword', keyword)
  }

  // 发起API请求
  fetch(`http://localhost:8000/api/dashboard?${params}`)
    .then(res => res.json())
    .then(data => {
      // 更新图表数据
    })
}

const initCharts = async () => {
  const apiBase = '/api/user'

  try {
    // 加载统计数据
    const statsRes = await request.get(`${apiBase}/stats`)
    if (statsRes.data.code === 200) {
      const stats = statsRes.data.data
      userStats.value = [
        { label: '平均PageRank', value: stats.avg_pagerank, icon: 'Star', color: 'blue' },
        { label: '网络密度', value: stats.network_density, icon: 'Share', color: 'green' },
        { label: '核心节点数', value: stats.core_nodes, icon: 'UserFilled', color: 'orange' },
        { label: '传播层级', value: stats.propagation_levels, icon: 'Histogram', color: 'purple' }
      ]
    }

    // 加载列表
    const listRes = await request.get(`${apiBase}/list?page_size=10`)
    userList.value = listRes.data.data.users

    // 1. 绘制网络图
    const netRes = await request.get(`${apiBase}/network?top_n=30`)
    if (netRes.data.code === 200 && netRes.data.data.nodes.length > 0) {
      const netChart = echarts.init(networkChartRef.value)
      netChart.setOption({
        tooltip: {},
        legend: [{
          data: ['核心传播者', '意见领袖', '活跃参与者', '潜力用户', '普通用户']
        }],
        series: [{
          type: 'graph',
          layout: 'force',
          symbolSize: 20,
          roam: true,
          label: { show: true, position: 'right' },
          force: { repulsion: 150, edgeLength: 100 },
          categories: [
            { name: '核心传播者' },
            { name: '意见领袖' },
            { name: '活跃参与者' },
            { name: '潜力用户' },
            { name: '普通用户' }
          ],
          data: netRes.data.data.nodes.map(node => ({
            ...node,
            category: node.category
          })),
          links: netRes.data.data.links,
          lineStyle: {
            color: 'source',
            curveness: 0.1
          }
        }]
      })
    }

    // 2. 绘制角色分布饼图
    const roleRes = await request.get(`${apiBase}/role-distribution`)
    if (roleRes.data.code === 200 && roleRes.data.data.length > 0) {
      const roleChart = echarts.init(roleChartRef.value)
      roleChart.setOption({
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left' },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: true,
            formatter: '{b}: {c} ({d}%)'
          },
          data: roleRes.data.data
        }]
      })
    }
  } catch (error) {
    console.error('加载用户数据失败:', error)
  }
}

onMounted(() => {
  initCharts()
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
