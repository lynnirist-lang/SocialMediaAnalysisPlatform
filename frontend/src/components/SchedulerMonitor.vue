<template>
  <div class="scheduler-monitor">
    <!-- Row 1 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <!-- 数据爬取状态 -->
      <el-col :span="12">
        <div class="status-card">
          <div class="card-header">数据爬取状态（MediaCrawler）</div>
          <div v-if="crawlerFiles.length === 0" class="empty-tip">暂无数据文件</div>
          <el-table
            v-else
            :data="crawlerFiles"
            size="small"
            stripe
            style="width: 100%"
          >
            <el-table-column prop="filename" label="文件名" min-width="180" show-overflow-tooltip />
            <el-table-column prop="mtime" label="修改时间" width="160" />
            <el-table-column label="大小" width="90" align="right">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
          </el-table>
          <div class="refresh-hint">每 30 秒自动刷新</div>
        </div>
      </el-col>

      <!-- 调度分析状态 -->
      <el-col :span="12">
        <div class="status-card">
          <div class="card-header">数据分析调度状态</div>

          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="运行状态">
              <el-tag :type="schedulerStatus.is_running ? 'danger' : 'success'" size="small">
                {{ schedulerStatus.is_running ? '运行中' : '空闲' }}
              </el-tag>
            </el-descriptions-item>

            <el-descriptions-item label="任务启用">
              <el-switch
                v-model="taskEnabled"
                active-text="已启用"
                inactive-text="已禁用"
                @change="handleToggleEnabled"
              />
            </el-descriptions-item>

            <el-descriptions-item label="上次执行">
              <span v-if="schedulerStatus.last_run">
                {{ formatDatetime(schedulerStatus.last_run.start_time) }}
                &nbsp;
                <el-tag
                  :type="schedulerStatus.last_run.status === 'success' ? 'success' : 'danger'"
                  size="small"
                >
                  {{ schedulerStatus.last_run.status === 'success' ? '成功' : '失败' }}
                </el-tag>
              </span>
              <span v-else class="empty-tip">暂无执行记录</span>
            </el-descriptions-item>

            <el-descriptions-item label="下次计划">
              <span v-if="schedulerStatus.next_scheduled && schedulerStatus.next_scheduled.length">
                <el-tag
                  v-for="(t, idx) in schedulerStatus.next_scheduled"
                  :key="idx"
                  size="small"
                  style="margin-right: 6px"
                >
                  {{ formatScheduledTime(t) }}
                </el-tag>
              </span>
              <span v-else class="empty-tip">暂无计划</span>
            </el-descriptions-item>
          </el-descriptions>

          <div style="margin-top: 16px">
            <el-button type="primary" size="small" :loading="triggering" @click="handleTrigger">
              手动触发
            </el-button>
          </div>

          <div class="refresh-hint">每 15 秒自动刷新</div>
        </div>
      </el-col>
    </el-row>

    <!-- Row 2: 执行历史 -->
    <el-row>
      <el-col :span="24">
        <div class="status-card">
          <div class="card-header">执行历史</div>
          <div v-if="!history.length" class="empty-tip">暂无执行历史</div>
          <el-table v-else :data="history" size="small" stripe style="width: 100%">
            <el-table-column label="开始时间" width="160">
              <template #default="{ row }">{{ formatDatetime(row.start_time) }}</template>
            </el-table-column>
            <el-table-column label="结束时间" width="160">
              <template #default="{ row }">{{ formatDatetime(row.end_time) }}</template>
            </el-table-column>
            <el-table-column label="爬虫" width="90" align="center">
              <template #default="{ row }">
                <span v-if="!row.crawler || row.crawler.status === 'skipped'" style="color:#ccc;font-size:12px">跳过</span>
                <el-tooltip v-else :content="row.crawler.message" placement="top">
                  <el-tag
                    :type="row.crawler.status === 'success' ? 'success' : row.crawler.status === 'timeout' ? 'warning' : 'danger'"
                    size="small"
                  >
                    {{ crawlerStatusLabel(row.crawler.status) }}
                  </el-tag>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="分析" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                  {{ row.status === 'success' ? '成功' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="帖子(原始)" width="90" align="right">
              <template #default="{ row }">{{ row.stats?.posts_raw ?? row.stats?.posts ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="耗时(分钟)" width="100" align="right">
              <template #default="{ row }">{{ calcDuration(row.start_time, row.end_time) }}</template>
            </el-table-column>
            <el-table-column label="错误信息" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.error" class="error-text">{{ row.error }}</span>
                <span v-else class="empty-tip">-</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api/request'

// ── State ──────────────────────────────────────────────────────────────────
const schedulerStatus = ref({
  is_running: false,
  pid: null,
  last_run: null,
  next_scheduled: [],
  history: [],
})
const crawlerFiles = ref([])
const taskEnabled = ref(true)
const triggering = ref(false)

let statusTimer = null
let crawlerTimer = null

// ── Computed ───────────────────────────────────────────────────────────────
const history = computed(() => {
  const h = schedulerStatus.value.history || []
  return h.slice(-10).reverse()
})

// ── Helpers ────────────────────────────────────────────────────────────────
function formatDatetime(str) {
  if (!str) return '-'
  // "2024-01-01T12:00:00" → "2024-01-01 12:00:00"
  return str.replace('T', ' ').split('.')[0]
}

function formatScheduledTime(str) {
  if (!str) return '-'
  const today = new Date().toISOString().slice(0, 10)
  const [datePart, timePart] = str.split('T')
  if (!timePart) return str
  const time = timePart.slice(0, 5)  // "12:00"
  if (datePart === today) return `今日${time}`
  return `${datePart} ${time}`
}

function formatSize(bytes) {
  if (bytes === undefined || bytes === null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function crawlerStatusLabel(status) {
  const map = { success: '成功', failed: '失败', timeout: '超时', skipped: '跳过' }
  return map[status] ?? status
}

function calcDuration(start, end) {
  if (!start || !end) return '-'
  const s = new Date(start.replace('T', ' '))
  const e = new Date(end.replace('T', ' '))
  const diff = (e - s) / 60000
  if (isNaN(diff)) return '-'
  return diff.toFixed(1)
}

// ── API calls ──────────────────────────────────────────────────────────────
async function fetchStatus() {
  try {
    const res = await request.get('/api/scheduler/status')
    const data = res.data?.data || res.data
    schedulerStatus.value = data
    // Sync the enabled switch from control file via the response
    // (backend doesn't return enabled directly in status; use taskEnabled's current value if not in response)
    if (typeof data.enabled === 'boolean') {
      taskEnabled.value = data.enabled
    }
  } catch (e) {
    console.error('fetchStatus error', e)
  }
}

async function fetchCrawlerFiles() {
  try {
    const res = await request.get('/api/scheduler/crawler-files')
    crawlerFiles.value = res.data?.data || []
  } catch (e) {
    console.error('fetchCrawlerFiles error', e)
  }
}

async function handleToggleEnabled(val) {
  try {
    const res = await request.post('/api/scheduler/toggle-enabled')
    const newVal = res.data?.enabled
    if (typeof newVal === 'boolean') {
      taskEnabled.value = newVal
    }
    ElMessage.success(`调度任务已${newVal ? '启用' : '禁用'}`)
  } catch (e) {
    ElMessage.error('操作失败')
    // Revert
    taskEnabled.value = !val
  }
}

async function handleTrigger() {
  triggering.value = true
  try {
    const res = await request.post('/api/scheduler/trigger')
    ElMessage.success(res.data?.message || '已开始执行')
    setTimeout(fetchStatus, 2000)
  } catch (e) {
    ElMessage.error('触发失败')
  } finally {
    triggering.value = false
  }
}

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(() => {
  fetchStatus()
  fetchCrawlerFiles()
  statusTimer = setInterval(fetchStatus, 15000)
  crawlerTimer = setInterval(fetchCrawlerFiles, 30000)
})

onUnmounted(() => {
  clearInterval(statusTimer)
  clearInterval(crawlerTimer)
})
</script>

<style scoped>
.scheduler-monitor {
  padding: 4px 0;
}

.status-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  height: 100%;
}

.card-header {
  font-weight: bold;
  font-size: 15px;
  margin-bottom: 15px;
  border-left: 4px solid #409eff;
  padding-left: 10px;
}

.empty-tip {
  color: #999;
  font-size: 13px;
  padding: 8px 0;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}

.refresh-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #c0c4cc;
  text-align: right;
}
</style>
