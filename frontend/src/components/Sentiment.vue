<template>
  <div class="sentiment-container">
    <el-row :gutter="20">
       <!-- 左侧：情感趋势图 -->
      <el-col :span="10">
        <div class="chart-card">
          <div class="card-header">情感得分趋势</div>
          <div ref="lineChartRef" style="height: 400px"></div>
        </div>
      </el-col>

      <!-- 中间：活跃热力图 -->
      <el-col :span="14">
        <div class="chart-card">
          <div class="card-header">活跃热力图 (24h/周)</div>
          <div ref="heatmapRef" style="height: 400px"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 底部：典型博文列表 -->
    <el-row style="margin-top: 20px">
      <el-col :span="24">
        <div class="chart-card">
          <div class="card-header">典型博文监控</div>
          <el-table :data="postList" stripe style="width: 100%" v-loading="loading">
            <el-table-column prop="create_time" label="发布时间" width="180" />
            <el-table-column prop="content" label="博文内容" show-overflow-tooltip />
            <el-table-column label="情感倾向" width="100">
              <template #default="scope">
                <el-tag :type="getSentimentTag(scope.row.sentiment)" size="small">
                  {{ scope.row.sentiment }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="得分" width="80">
              <template #default="scope">
                <span :style="{ color: getScoreColor(scope.row.sentiment_score) }">
                  {{ scope.row.sentiment_score?.toFixed(2) || '0.00' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="scope">
                <el-button
                  v-if="scope.row.note_id"
                  type="primary"
                  size="small"
                  link
                  @click="openWeibo(scope.row.note_id)"
                >
                  查看原博
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject, watch } from 'vue'
import * as echarts from 'echarts'
import request from '../api/request'

const API_BASE = '/api/sentiment'
const loading = ref(false)
const postList = ref([])
const globalDateRange = inject('globalDateRange')
const globalSearch = inject('globalSearch')

const lineChartRef = ref(null)
const heatmapRef = ref(null)

let lineChart = null
let heatmapChart = null

const buildQS = (dateRange, keyword) => {
  const p = new URLSearchParams()
  if (dateRange?.length === 2) {
    const fmt = d => d instanceof Date ? d.toISOString().split('T')[0] : String(d)
    p.append('start_date', fmt(dateRange[0]))
    p.append('end_date', fmt(dateRange[1]))
  }
  if (keyword) p.append('keyword', keyword)
  const s = p.toString()
  return s ? `?${s}` : ''
}

const updateLineChart = async (dateRange, keyword) => {
  if (!lineChart) return
  try {
    const res = await request.get(`${API_BASE}/trend${buildQS(dateRange, keyword)}`)
    const { dates, scores } = res.data.data
    const minScore = scores.length ? Math.min(...scores) : -1
    const maxScore = scores.length ? Math.max(...scores) : 1
    const pad = 0.1
    lineChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: dates, boundaryGap: false },
      yAxis: { type: 'value', min: Math.floor((minScore - pad) * 10) / 10, max: Math.ceil((maxScore + pad) * 10) / 10 },
      series: [{
        name: '情感得分',
        type: 'line',
        smooth: true,
        data: scores,
        areaStyle: { opacity: 0.2, color: '#409EFF' },
        lineStyle: { color: '#409EFF', width: 2 },
        itemStyle: { color: '#409EFF' }
      }]
    })
  } catch (e) { console.error('LineChart error:', e) }
}

const updateHeatmap = async () => {
  if (!heatmapChart) return
  try {
    const res = await request.get(`${API_BASE}/heatmap`)
    const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)
    const days = ['周日', '周六', '周五', '周四', '周三', '周二', '周一']
    const heatData = res.data.data
    const maxVal = Math.max(...heatData.map(d => d[2]), 1)

    heatmapChart.setOption({
      tooltip: { position: 'top' },
      grid: { height: '80%', top: '5%', bottom: '15%' },
      xAxis: { type: 'category', data: hours, boundaryGap: true, splitLine: { show: true, lineStyle: { type: 'dashed' } } },
      yAxis: { type: 'category', data: days, boundaryGap: true },
      visualMap: {
        min: 0, max: maxVal, orient: 'horizontal', left: 'center', bottom: '0',
        inRange: { color: ['#ebedf0', '#c6e48b', '#7bc96f', '#239a3b', '#196127'] },
        textStyle: { fontSize: 10 }
      },
      series: [{ type: 'heatmap', data: heatData, label: { show: true, fontSize: 10, color: '#333' } }]
    })
  } catch (e) { console.error('Heatmap error:', e) }
}

const fetchPosts = async (dateRange, keyword) => {
  loading.value = true
  try {
    const res = await request.get(`${API_BASE}/posts?page_size=10${buildQS(dateRange, keyword).replace('?', '&')}`)
    postList.value = res.data.data?.posts || []
  } catch (e) { console.error(e) }
  loading.value = false
}

const loadData = (dateRange, keyword) => {
  updateLineChart(dateRange, keyword)
  updateHeatmap()
  fetchPosts(dateRange, keyword)
}

watch([globalDateRange, globalSearch], ([newDates, newKeyword]) => {
  loadData(newDates, newKeyword)
}, { deep: true })

const getSentimentTag = (s) => s === '积极' ? 'success' : s === '消极' ? 'danger' : 'warning'
const getScoreColor = (score) => score > 0.6 ? '#67C23A' : score < 0.4 ? '#F56C6C' : '#E6A23C'

const openWeibo = (noteId) => {
  if (!noteId) return
  window.open(`https://m.weibo.cn/detail/${noteId}`, '_blank')
}

const handleResize = () => {
  lineChart?.resize()
  heatmapChart?.resize()
}

onMounted(() => {
  lineChart = echarts.init(lineChartRef.value)
  heatmapChart = echarts.init(heatmapRef.value)
  loadData(globalDateRange?.value, globalSearch?.value)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  lineChart?.dispose()
  heatmapChart?.dispose()
})
</script>

<style scoped>
.sentiment-container {
  padding: 10px;
}

.chart-card {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  height: 100%;
}

.card-header {
  font-weight: bold;
  margin-bottom: 15px;
  border-left: 4px solid #409EFF;
  padding-left: 10px;
}
</style>
