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
            <div style="display:flex;align-items:center;gap:8px;">
              <el-tag v-if="dtmGeneratedAt" size="small" type="info" style="font-weight:normal">
                {{ dtmGeneratedAt }}
              </el-tag>
              <el-radio-group v-model="dtmView" size="small" @change="renderDtmChart">
                <el-radio-button value="sankey">演化图</el-radio-button>
                <el-radio-button value="trend">频率趋势</el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <div v-if="dtmEmpty" class="dtm-empty">
            <el-empty description="暂无 DTM 数据，请先运行 run_dynamic_topic.py" :image-size="80" />
          </div>
          <div v-show="!dtmEmpty" ref="topicEvolutionRef" style="height: 460px;"></div>
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
import { ref, onMounted, onUnmounted, inject, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import request from '../api/request'

const globalDateRange = inject('globalDateRange')
const globalSearch = inject('globalSearch')

const topicEvolutionRef = ref(null)
const roleChartRef = ref(null)
const userList = ref([])
const userStats = ref([
  { label: '平均PageRank', value: '-', icon: 'Star', color: 'blue' },
  { label: '网络密度', value: '-', icon: 'Share', color: 'green' },
  { label: '核心节点数', value: '-', icon: 'UserFilled', color: 'orange' },
  { label: '传播层级', value: '-', icon: 'Histogram', color: 'purple' }
])

// DTM 状态
const dtmView = ref('sankey')      // 'sankey' | 'trend'
const dtmEmpty = ref(false)
const dtmGeneratedAt = ref('')
let _dtmData = null                // 缓存 API 返回

let topicEvolutionChart = null
let roleChart = null

// ── 辅助：从节点名提取显示文本 ────────────────────────────────────────────
// 节点名格式 "{period}::{chain_name}_{chain_id}"
function _nodeLabel(name) {
  const parts = name.split('::')
  if (parts.length < 2) return name
  // 去掉末尾的 "_数字" id 后缀
  return parts[1].replace(/_\d+$/, '')
}

// ── Sankey 渲染 ───────────────────────────────────────────────────────────
function _renderSankey(data) {
  const { sankey, periods } = data
  if (!sankey.nodes.length) {
    topicEvolutionChart.setOption({
      title: { text: '暂无演化数据', left: 'center', top: 'middle',
               textStyle: { color: '#ccc', fontSize: 14 } }
    }, true)
    return
  }

  topicEvolutionChart.setOption({
    backgroundColor: '#fff',
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          const period = params.name.split('::')[0]
          return `${_nodeLabel(params.name)}<br/>期间：${period}`
        }
        // link
        const kws = (params.data.keywords || []).join('、')
        return `${_nodeLabel(params.data.source)} → ${_nodeLabel(params.data.target)}<br/>` +
               `文档数：${params.value}<br/>关键词：${kws}`
      }
    },
    series: [{
      type: 'sankey',
      layout: 'none',
      emphasis: { focus: 'adjacency' },
      nodeAlign: 'left',
      nodeGap: 12,
      nodeWidth: 20,
      data: sankey.nodes,
      links: sankey.links,
      label: {
        position: 'right',
        formatter: (p) => _nodeLabel(p.name),
        fontSize: 12,
        color: '#444',
      },
      lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.4 },
      itemStyle: { borderWidth: 0 },
    }]
  }, true)
}

// ── Trend 渲染 ────────────────────────────────────────────────────────────
function _renderTrend(data) {
  const { periods, trend } = data
  if (!trend.series.length) {
    topicEvolutionChart.setOption({
      title: { text: '暂无频率数据', left: 'center', top: 'middle',
               textStyle: { color: '#ccc', fontSize: 14 } }
    }, true)
    return
  }

  topicEvolutionChart.setOption({
    backgroundColor: '#fff',
    tooltip: { trigger: 'axis' },
    legend: { data: trend.series.map(s => s.name), top: 0, type: 'scroll' },
    grid: { top: 40, bottom: 40, left: 50, right: 20 },
    xAxis: {
      type: 'category',
      data: periods,
      axisLabel: { rotate: 30, fontSize: 11 }
    },
    yAxis: { type: 'value', name: '文档数', minInterval: 1 },
    series: trend.series.map(s => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      symbolSize: 6,
      lineStyle: { width: 2 },
      emphasis: { focus: 'series' },
    }))
  }, true)
}

// ── 主渲染入口（tab 切换复用）────────────────────────────────────────────
const renderDtmChart = () => {
  if (!topicEvolutionChart || !_dtmData) return
  if (dtmView.value === 'sankey') {
    _renderSankey(_dtmData)
  } else {
    _renderTrend(_dtmData)
  }
}

// ── DTM 数据加载 ──────────────────────────────────────────────────────────
const loadDynamicTopics = async () => {
  try {
    const res = await request.get('/api/topic/dynamic-evolution')
    if (res.data.code !== 200) {
      dtmEmpty.value = true
      return
    }
    _dtmData = res.data.data
    dtmEmpty.value = false
    const at = _dtmData.generated_at
    dtmGeneratedAt.value = at ? `数据更新：${at.replace('T', ' ')}` : ''
    await nextTick()
    if (!topicEvolutionChart && topicEvolutionRef.value) {
      topicEvolutionChart = echarts.init(topicEvolutionRef.value)
    }
    renderDtmChart()
  } catch (e) {
    dtmEmpty.value = true
    console.error('加载 DTM 数据失败:', e)
  }
}

// ── 角色 / 情感 工具函数 ─────────────────────────────────────────────────
const getRoleTagType = (role) => {
  const typeMap = { '核心传播者': 'danger', '意见领袖': 'warning',
                    '活跃参与者': 'success', '潜力用户': 'primary', '普通用户': 'info' }
  return typeMap[role] || 'info'
}
const getSentimentTagType = (t) => t === '积极' ? 'success' : t === '消极' ? 'danger' : 'info'
const activityColor = (score) => {
  const v = score ?? 0
  return v >= 70 ? '#67C23A' : v >= 40 ? '#E6A23C' : '#909399'
}

// ── 主数据加载 ────────────────────────────────────────────────────────────
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
        { label: '平均PageRank', value: s.avg_pagerank, icon: 'Star', color: 'blue' },
        { label: '网络密度', value: s.network_density, icon: 'Share', color: 'green' },
        { label: '核心节点数', value: s.core_nodes, icon: 'UserFilled', color: 'orange' },
        { label: '传播层级', value: s.propagation_levels, icon: 'Histogram', color: 'purple' }
      ]
    }

    userList.value = listRes.data.data?.users || []

    if (roleRes.data.code === 200 && roleRes.data.data.length > 0 && roleChart) {
      roleChart.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'horizontal', bottom: 0, left: 'center' },
        series: [{
          type: 'pie',
          radius: ['38%', '62%'],
          center: ['50%', '45%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: true, formatter: '{b}\n{d}%', lineHeight: 18 },
          labelLine: { length: 12, length2: 8, smooth: true },
          data: roleRes.data.data
        }]
      })
    }
  } catch (e) {
    console.error('加载用户数据失败:', e)
  }
}

watch([globalDateRange, globalSearch], () => { loadData() }, { deep: true })

const handleResize = () => {
  topicEvolutionChart?.resize()
  roleChart?.resize()
}

onMounted(async () => {
  roleChart = echarts.init(roleChartRef.value)
  await Promise.all([loadData(), loadDynamicTopics()])
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
.dtm-empty { display: flex; justify-content: center; align-items: center; height: 460px; }

.blue { color: #409EFF; }
.green { color: #67C23A; }
.orange { color: #E6A23C; }
.purple { color: #9b59b6; }
</style>
