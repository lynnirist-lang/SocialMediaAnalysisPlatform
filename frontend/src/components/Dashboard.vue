<template>
  <div class="dashboard-container">
    <el-row :gutter="20">
      <el-col :span="8">
        <div class="card-panel">
          <div class="card-info">
            <div class="card-title">总博文数</div>
            <div class="card-value">{{ summary.total_posts?.toLocaleString() || 0 }}</div>
          </div>
          <el-icon class="card-icon blue"><Document /></el-icon>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="card-panel">
          <div class="card-info">
            <div class="card-title">参与用户数</div>
            <div class="card-value">{{ summary.total_users?.toLocaleString() || 0 }}</div>
          </div>
          <el-icon class="card-icon green"><UserFilled /></el-icon>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="card-panel">
          <div class="card-info">
            <div class="card-title">总评论数</div>
            <div class="card-value">{{ summary.total_comments?.toLocaleString() || 0 }}</div>
          </div>
          <el-icon class="card-icon orange"><ChatDotRound /></el-icon>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <div class="chart-wrapper">
          <div class="chart-header">舆情演变趋势</div>
          <div ref="trendChartRef" style="height: 350px;"></div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="chart-wrapper">
          <div class="chart-header">情感分布占比</div>
          <div ref="pieChartRef" style="height: 350px;"></div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <div class="chart-wrapper">
          <div class="chart-header">热点词云图</div>
          <div ref="wordCloudRef" style="height: 400px;"></div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject, watch } from 'vue'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import request from '../api/request'

const API_BASE = '/api/dashboard'
const globalDateRange = inject('globalDateRange')
const globalSearch = inject('globalSearch')
const summary = ref({})
const trendChartRef = ref(null)
const pieChartRef = ref(null)
const wordCloudRef = ref(null)

let trendChart = null
let pieChart = null
let wordCloudChart = null

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

const fetchSummary = async (dateRange, keyword) => {
  try {
    const res = await request.get(`${API_BASE}/summary${buildQS(dateRange, keyword)}`)
    summary.value = res.data.data
  } catch (e) { console.error('Summary error:', e) }
}

const updateTrendChart = async (dateRange, keyword) => {
  if (!trendChart) return
  try {
    const res = await request.get(`${API_BASE}/trend${buildQS(dateRange, keyword)}`)
    const { dates, post_counts, user_counts } = res.data.data
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['博文数', '用户数'], bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: dates, boundaryGap: false },
      yAxis: { type: 'value' },
      series: [
        { name: '博文数', type: 'line', smooth: true, data: post_counts, areaStyle: { opacity: 0.1 } },
        { name: '用户数', type: 'line', smooth: true, data: user_counts }
      ]
    })
  } catch (e) { console.error('Trend error:', e) }
}

const updatePieChart = async () => {
  if (!pieChart) return
  try {
    const res = await request.get('/api/sentiment/distribution')
    const data = res.data.data
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: '0', left: 'center', itemGap: 10 },
      series: [{
        type: 'pie',
        radius: ['35%', '48%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        label: { show: true, position: 'outside', formatter: '{b}', fontSize: 12, color: '#666' },
        labelLine: { show: true, length: 15, length2: 10, smooth: true },
        data: [
          { value: data.positive, name: '积极', itemStyle: { color: '#67C23A' } },
          { value: data.neutral, name: '中性', itemStyle: { color: '#E6A23C' } },
          { value: data.negative, name: '消极', itemStyle: { color: '#F56C6C' } }
        ]
      }]
    })
  } catch (e) { console.error('Pie error:', e) }
}

const updateWordCloud = async () => {
  if (!wordCloudChart) return
  try {
    const res = await request.get(`${API_BASE}/wordcloud`)
    wordCloudChart.setOption({
      series: [{
        type: 'wordCloud',
        shape: 'circle',
        sizeRange: [12, 50],
        rotationRange: [0, 0],
        gridSize: 4,
        drawOutOfBound: false,
        layoutAnimation: true,
        data: res.data.data,
        textStyle: {
          fontFamily: 'sans-serif',
          fontWeight: 'bold',
          color: () => `rgb(${[
            Math.round(Math.random() * 160),
            Math.round(Math.random() * 160),
            Math.round(Math.random() * 160)
          ].join(',')})`
        },
        emphasis: { textStyle: { shadowBlur: 10, shadowColor: '#333' } }
      }]
    })
  } catch (e) { console.error('WordCloud error:', e) }
}

const loadData = (dateRange, keyword) => {
  fetchSummary(dateRange, keyword)
  updateTrendChart(dateRange, keyword)
  updatePieChart()
  updateWordCloud()
}

watch([globalDateRange, globalSearch], ([newDates, newKeyword]) => {
  loadData(newDates, newKeyword)
}, { deep: true })

const handleResize = () => {
  trendChart?.resize()
  pieChart?.resize()
  wordCloudChart?.resize()
}

onMounted(() => {
  trendChart = echarts.init(trendChartRef.value)
  pieChart = echarts.init(pieChartRef.value)
  wordCloudChart = echarts.init(wordCloudRef.value)
  loadData(globalDateRange?.value, globalSearch?.value)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
  wordCloudChart?.dispose()
})
</script>

<style scoped>
.dashboard-container {
  padding: 10px; /* 稍微缩小边距 */
  background-color: #f5f7fa;
}

.card-panel {
  background: #fff;
  padding: 25px;
  border-radius: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.card-title { font-size: 14px; color: #909399; }
.card-value { font-size: 26px; font-weight: bold; margin-top: 8px; }
.card-icon { font-size: 48px; opacity: 0.2; }

.chart-wrapper {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.chart-header {
  font-weight: bold;
  margin-bottom: 20px;
  border-left: 4px solid #409EFF;
  padding-left: 10px;
}

.blue { color: #409EFF; }
.green { color: #67C23A; }
.orange { color: #E6A23C; }
</style>