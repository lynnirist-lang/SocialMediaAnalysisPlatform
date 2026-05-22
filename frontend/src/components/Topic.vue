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

// 1. 获取排行榜
const fetchRank = async () => {
  const res = await request.get(`${API_BASE}/keywords?top_n=10`)
  if (res.data.code === 200) keywordRank.value = res.data.data
}

// 2. 初始化聚类图 (对应截图左侧)
const initCluster = async () => {
  const myChart = echarts.init(clusterChartRef.value)
  const res = await request.get(`${API_BASE}/clusters`)
  if (res.data.code === 200) {
    const { nodes, links, categories } = res.data.data
    myChart.setOption({
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
    charts.push(myChart)
  }
}

// 3. 初始化情感分布柱状图 (对应截图右下)
const initBar = async () => {
  const myChart = echarts.init(barChartRef.value)
  const res = await request.get(`${API_BASE}/bar`)
  if (res.data.code === 200) {
    const { topics, categories, positive, neutral, negative } = res.data.data

    // 组合话题名和分类，例如："明星角色塑造与时尚多元 (娱乐八卦)"
    const displayLabels = topics.map((topic, index) => {
      return `${categories[index]}`
    })

    myChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0, icon: 'circle' },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: displayLabels, // 使用带分类的标签
        axisLabel: {
          interval: 0,
          formatter: (value) => {
            // 如果标签太长，可以换行显示
            return value.length > 15 ? value.substring(0, 15) + '...' : value
          }
        }
      },
      series: [
        { name: '积极', type: 'bar', stack: 'total', color: '#67C23A', data: positive },
        { name: '中性', type: 'bar', stack: 'total', color: '#E6A23C', data: neutral },
        { name: '消极', type: 'bar', stack: 'total', color: '#F56C6C', data: negative }
      ]
    })
    charts.push(myChart)
  }
}

onMounted(() => {
  fetchRank(); initCluster(); initBar();
  window.addEventListener('resize', () => charts.forEach(c => c.resize()))
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