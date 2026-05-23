<template>
  <div class="topic-page">
    <el-row :gutter="20">
      <!-- 左侧：主题聚类图 -->
      <el-col :span="14">
        <div class="tp-card main-chart-card">
          <div class="card-header">主题聚类分析</div>
          <div ref="clusterChartRef" style="height:690px;"></div>
        </div>
      </el-col>

      <!-- 右侧：DTM 演化 + 情感分布 -->
      <el-col :span="10">
        <div class="tp-card dtm-card">
          <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">
            <span>动态主题演化</span>
            <div style="display:flex;align-items:center;gap:8px;">
              <el-tag v-if="dtmGeneratedAt" size="small" type="info" style="font-weight:normal;">{{ dtmGeneratedAt }}</el-tag>
              <el-radio-group v-model="dtmView" size="small" @change="renderDtmChart">
                <el-radio-button value="sankey">演化图</el-radio-button>
                <el-radio-button value="trend">趋势</el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <div v-if="dtmEmpty" style="display:flex;justify-content:center;align-items:center;height:290px;">
            <el-empty description="暂无 DTM 数据，请先运行 run_dynamic_topic.py" :image-size="60" />
          </div>
          <div v-show="!dtmEmpty" ref="dtmChartRef" style="height:290px;"></div>
        </div>

        <div class="tp-card bar-card">
          <div class="card-header">各话题情感倾向</div>
          <div ref="barChartRef" style="height:330px;"></div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import request from '../api/request'

const API_BASE = '/api/topic'
const clusterChartRef = ref(null)
const barChartRef = ref(null)
const dtmChartRef = ref(null)
const globalDateRange = inject('globalDateRange')
const globalSearch = inject('globalSearch')

const dtmView = ref('sankey')
const dtmEmpty = ref(false)
const dtmGeneratedAt = ref('')
let _dtmData = null

let clusterChart = null
let barChart = null
let dtmChart = null

const PALETTE = ['#3b7dd8', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16']

// ── DTM helpers ──────────────────────────────────────────────────────────────
function _nodeLabel(name) {
  const parts = name.split('::')
  return parts.length < 2 ? name : parts[1].replace(/_\d+$/, '')
}

function _renderSankey(data) {
  const { sankey } = data
  if (!sankey.nodes.length) {
    dtmChart.setOption({ title: { text: '暂无演化数据', left: 'center', top: 'middle', textStyle: { color: '#aaa', fontSize: 13 } } }, true)
    return
  }
  dtmChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: p => {
        if (p.dataType === 'node') return `<b>${_nodeLabel(p.name)}</b><br/>时期：${p.name.split('::')[0]}`
        const kws = (p.data.keywords || []).join('、')
        return `${_nodeLabel(p.data.source)} → ${_nodeLabel(p.data.target)}<br/>文档数：${p.value}<br/>关键词：${kws}`
      }
    },
    series: [{
      type: 'sankey',
      layout: 'none',
      emphasis: { focus: 'adjacency' },
      nodeAlign: 'left',
      nodeGap: 10,
      nodeWidth: 16,
      data: sankey.nodes,
      links: sankey.links,
      label: { position: 'right', formatter: p => _nodeLabel(p.name), fontSize: 11, color: '#1a2a4a' },
      lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.4 },
      itemStyle: { borderWidth: 0 },
    }]
  }, true)
}

function _renderTrend(data) {
  const { periods, trend } = data
  if (!trend.series.length) {
    dtmChart.setOption({ title: { text: '暂无趋势数据', left: 'center', top: 'middle', textStyle: { color: '#aaa', fontSize: 13 } } }, true)
    return
  }
  dtmChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: trend.series.map(s => s.name), top: 0, type: 'scroll', textStyle: { fontSize: 10 } },
    grid: { top: 36, bottom: 28, left: 44, right: 12 },
    xAxis: { type: 'category', data: periods, axisLabel: { rotate: 20, fontSize: 10 } },
    yAxis: { type: 'value', name: '文档数', minInterval: 1, nameTextStyle: { fontSize: 10 } },
    series: trend.series.map((s, i) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      symbolSize: 5,
      lineStyle: { width: 2, color: PALETTE[i % PALETTE.length] },
      itemStyle: { color: PALETTE[i % PALETTE.length] },
      emphasis: { focus: 'series' },
    }))
  }, true)
}

const renderDtmChart = () => {
  if (!dtmChart || !_dtmData) return
  dtmView.value === 'sankey' ? _renderSankey(_dtmData) : _renderTrend(_dtmData)
}

const loadDynamicTopics = async () => {
  try {
    const res = await request.get('/api/topic/dynamic-evolution')
    if (res.data.code !== 200) { dtmEmpty.value = true; return }
    _dtmData = res.data.data
    dtmEmpty.value = false
    const at = _dtmData.generated_at
    dtmGeneratedAt.value = at ? `更新：${at.replace('T', ' ')}` : ''
    await nextTick()
    if (!dtmChart && dtmChartRef.value) dtmChart = echarts.init(dtmChartRef.value)
    renderDtmChart()
  } catch (e) {
    dtmEmpty.value = true
    console.error('DTM error:', e)
  }
}

// ── Cluster ──────────────────────────────────────────────────────────────────
const updateCluster = async () => {
  if (!clusterChart) return
  try {
    const res = await request.get(`${API_BASE}/clusters`)
    if (res.data.code === 200) {
      const { nodes, links, categories } = res.data.data
      clusterChart.setOption({
        tooltip: { formatter: p => p.dataType === 'node' ? `<b>${p.name}</b><br/>热度：${p.value}` : '' },
        legend: [{ data: categories.map(a => a.name), bottom: 4, textStyle: { fontSize: 12 } }],
        series: [{
          type: 'graph',
          layout: 'force',
          data: nodes.map(n => ({ ...n, itemStyle: { color: PALETTE[n.category ?? 0] } })),
          links,
          categories: categories.map((c, i) => ({ name: c.name, itemStyle: { color: PALETTE[i] } })),
          roam: true,
          label: { show: true, position: 'right', fontSize: 11, color: '#1a2a4a' },
          force: { repulsion: 130, edgeLength: [40, 90] },
          lineStyle: { color: '#c8d8ea', width: 1 },
          emphasis: { focus: 'adjacency' },
        }]
      })
    }
  } catch (e) { console.error('Cluster error:', e) }
}

// ── Bar ───────────────────────────────────────────────────────────────────────
const updateBar = async () => {
  if (!barChart) return
  try {
    const res = await request.get(`${API_BASE}/bar`)
    if (res.data.code === 200) {
      const { categories, positive, neutral, negative } = res.data.data
      barChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { bottom: 0, icon: 'circle', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '14%', containLabel: true },
        xAxis: { type: 'value' },
        yAxis: {
          type: 'category',
          data: categories,
          axisLabel: { formatter: v => v.length > 12 ? v.slice(0, 12) + '…' : v, fontSize: 11 }
        },
        series: [
          { name: '积极', type: 'bar', stack: 'total', itemStyle: { color: '#10b981' }, data: positive },
          { name: '中性', type: 'bar', stack: 'total', itemStyle: { color: '#f59e0b' }, data: neutral },
          { name: '消极', type: 'bar', stack: 'total', itemStyle: { color: '#ef4444' }, data: negative },
        ]
      })
    }
  } catch (e) { console.error('Bar error:', e) }
}

const loadData = () => {
  updateCluster()
  updateBar()
  loadDynamicTopics()
}

watch([globalDateRange, globalSearch], () => loadData(), { deep: true })

const handleResize = () => {
  clusterChart?.resize()
  barChart?.resize()
  dtmChart?.resize()
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
  dtmChart?.dispose()
})
</script>

<style scoped>
.topic-page { padding: 4px; }

.tp-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 1px 8px rgba(0, 30, 70, 0.08);
  margin-bottom: 20px;
}

.main-chart-card { height: 750px; }
.dtm-card { height: 355px; }
.bar-card { height: 375px; }

.card-header {
  font-size: 15px;
  font-weight: 600;
  color: #1a2a4a;
  margin-bottom: 16px;
  padding-left: 10px;
  border-left: 4px solid #3b7dd8;
  line-height: 1.4;
}
</style>
