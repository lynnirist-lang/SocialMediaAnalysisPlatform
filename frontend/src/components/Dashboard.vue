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
            <div class="card-title">平均情感得分</div>
            <div class="card-value">{{ summary.avg_sentiment?.toFixed(2) || '0.00' }}</div>
          </div>
          <el-icon class="card-icon orange"><Trophy /></el-icon>
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
let charts = []

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

// 获取汇总数据
const fetchSummary = async () => {
  try {
    const res = await request.get(`${API_BASE}/summary`)
    summary.value = res.data.data
  } catch (e) { console.error("Summary error:", e) }
}

// 初始化趋势图
const initTrendChart = async () => {
  const myChart = echarts.init(trendChartRef.value)
  const res = await request.get(`${API_BASE}/trend`)
  const { dates, post_counts, user_counts } = res.data.data
  myChart.setOption({
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
  charts.push(myChart)
}

// 初始化饼图
// Dashboard.vue 里的 initPieChart 函数
const initPieChart = async () => {
  const myChart = echarts.init(pieChartRef.value)
  try {
    const res = await request.get('/api/sentiment/distribution')
    const data = res.data.data

    myChart.setOption({
      tooltip: { trigger: 'item' },
      legend: {
        bottom: '0',
        left: 'center',
        itemGap: 10 // 图例之间的间距
      },
      series: [{
        type: 'pie',
        // 关键修复 1：缩小半径，给外围文字留出足够空位 (从 70% 缩到 60%)
        radius: ['35%', '48%'],
        center: ['50%', '45%'], // 关键修复 2：圆心上移，给底部的图例留位置
        avoidLabelOverlap: true, // 关键修复 3：开启防重叠，防止标签挤在一起后消失
        label: {
          show: true,
          position: 'outside', // 确保标签在圆圈外面
          formatter: '{b}', // 展示名称和百分比
          fontSize: 12,
          color: '#666'
        },
        labelLine: {
          show: true,
          length: 15,    // 第一段引导线长度
          length2: 10,   // 第二段引导线长度
          smooth: true
        },
        data: [
          { value: data.positive, name: '积极', itemStyle: { color: '#67C23A' } },
          { value: data.neutral, name: '中性', itemStyle: { color: '#E6A23C' } },
          { value: data.negative, name: '消极', itemStyle: { color: '#F56C6C' } }
        ]
      }]
    })
    charts.push(myChart)
  } catch (e) { console.error(e) }
}
// 初始化词云
const initWordCloud = async () => {
  const myChart = echarts.init(wordCloudRef.value)
  const res = await request.get(`${API_BASE}/wordcloud`)

  myChart.setOption({
    series: [{
      type: 'wordCloud',
      shape: 'circle',
      // 1. 调整字号范围，缩小最大字号，能让更多词挤进来
      sizeRange: [12, 50],
      // 2. 调整旋转角度，设为 0 可以让词语全部水平显示，节省空间
      rotationRange: [0, 0],
      // 3. 调整网格间距，减小间距可以让词语靠得更近
      gridSize: 4,
      // 4. 关键：允许词语超出画布边缘（部分显示），从而强制渲染更多词
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
      emphasis: {
        textStyle: { shadowBlur: 10, shadowColor: '#333' }
      }
    }]
  })
  charts.push(myChart)
}

onMounted(() => {
  fetchSummary()
  initTrendChart()
  initPieChart()
  initWordCloud()
  window.addEventListener('resize', () => charts.forEach(c => c.resize()))
})

onUnmounted(() => {
  charts.forEach(c => c.dispose())
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