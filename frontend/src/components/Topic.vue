<template>
  <div class="topic-page">
    <el-row :gutter="20">
      <el-col :span="14">
        <div class="topic-card main-chart-card">
          <div class="card-header">主题聚类分析</div>
          <div ref="clusterChartRef" class="chart-content"></div>
        </div>
      </el-col>

      <el-col :span="10">
        <div class="topic-card rank-card">
          <div class="card-header">关键词排行榜</div>
          <el-table :data="keywordRank" size="small" height="300" stripe>
            <el-table-column type="index" label="排名" width="60" align="center">
              <template #default="scope">
                <span :class="['rank-badge', `rank-${scope.$index + 1}`]">{{ scope.$index + 1 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="word" label="关键词" />
            <el-table-column prop="count" label="热度值" width="100" />
            <el-table-column prop="topic" label="所属话题" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="topic-card bar-card">
          <div class="card-header">各话题情感倾向</div>
          <div ref="barChartRef" style="height: 320px;"></div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject, watch } from 'vue'
import * as echarts from 'echarts'
import request from '../api/request'

const API_BASE = '/api/topic'
const clusterChartRef = ref(null)
const barChartRef = ref(null)
const keywordRank = ref([])
const globalDateRange = inject('globalDateRange')
const globalSearch = inject('globalSearch')

let clusterChart = null
let barChart = null

const fetchRank = async () => {
  try {
    const res = await request.get(`${API_BASE}/keywords?top_n=10`)
    if (res.data.code === 200) keywordRank.value = res.data.data
  } catch (e) { console.error('Rank error:', e) }
}

const updateCluster = async () => {
  if (!clusterChart) return
  try {
    const res = await request.get(`${API_BASE}/clusters`)
    if (res.data.code === 200) {
      const { nodes, links, categories } = res.data.data
      clusterChart.setOption({
        tooltip: {},
        legend: [{ data: categories.map(a => a.name), bottom: 10 }],
        series: [{
          type: 'graph',
          layout: 'force',
          data: nodes,
          links: links,
          categories: categories,
          roam: true,
          label: { show: true, position: 'right' },
          force: { repulsion: 100, edgeLength: 50 }
        }]
      })
    }
  } catch (e) { console.error('Cluster error:', e) }
}

const updateBar = async () => {
  if (!barChart) return
  try {
    const res = await request.get(`${API_BASE}/bar`)
    if (res.data.code === 200) {
      const { topics, categories, positive, neutral, negative } = res.data.data
      const displayLabels = topics.map((_, i) => `${categories[i]}`)
      barChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { bottom: 0, icon: 'circle' },
        grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
        xAxis: { type: 'value' },
        yAxis: {
          type: 'category',
          data: displayLabels,
          axisLabel: {
            interval: 0,
            formatter: v => v.length > 15 ? v.substring(0, 15) + '...' : v
          }
        },
        series: [
          { name: '积极', type: 'bar', stack: 'total', color: '#67C23A', data: positive },
          { name: '中性', type: 'bar', stack: 'total', color: '#E6A23C', data: neutral },
          { name: '消极', type: 'bar', stack: 'total', color: '#F56C6C', data: negative }
        ]
      })
    }
  } catch (e) { console.error('Bar error:', e) }
}

const loadData = () => {
  fetchRank()
  updateCluster()
  updateBar()
}

watch([globalDateRange, globalSearch], () => {
  loadData()
}, { deep: true })

const handleResize = () => {
  clusterChart?.resize()
  barChart?.resize()
}

onMounted(() => {
  clusterChart = echarts.init(clusterChartRef.value)
  barChart = echarts.init(barChartRef.value)
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  clusterChart?.dispose()
  barChart?.dispose()
})
</script>

<style scoped>
.topic-card {
  background: #fff; padding: 20px; border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px;
}
.card-header {
  font-weight: 600; margin-bottom: 20px; border-left: 4px solid #409EFF; padding-left: 10px;
}
.main-chart-card { height: 750px; } /* 左侧拉高 */
.chart-content { height: 680px; }

/* 排名序号样式优化 */
.rank-badge {
  display: inline-block; width: 20px; height: 20px;
  line-height: 20px; text-align: center; border-radius: 50%;
  font-size: 12px; color: #fff; background: #909399;
}
.rank-1 { background: #f56c6c; }
.rank-2 { background: #e6a23c; }
.rank-3 { background: #409eff; }
</style>