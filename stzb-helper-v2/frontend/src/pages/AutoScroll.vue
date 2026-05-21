<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { NCard, NButton, NInput, NInputNumber, NSpace, NTag, NProgress, NAlert, NSpin, NEmpty, useMessage } from 'naive-ui'
import { LoadConfig, SaveConfig, CheckAdbConnection, GetAutoScrollStatus, StartAutoScroll, StopAutoScroll } from '../../wailsjs/go/main/App'
import { RefreshCw, Wifi, WifiOff, Play, Square, Save, Monitor } from 'lucide-vue-next'

const nmessage = useMessage()

const config = ref({
    adb_path: '',
    adb_serial: '',
    scroll_count: 8000,
    scroll_delay: 100,
    scroll_duration: 100
})

const defaultConfig = { ...config.value }

const loading = ref(false)
const checking = ref(false)
const adbConnected = ref(false)
const screenSize = ref('未知')
const status = ref({ running: false, current: 0, total: 0, screen_width: 1080, screen_height: 1920 })
const logs = ref([])
const starting = ref(false)
let statusTimer = null

const progressPercent = computed(() => {
    if (status.value.total === 0) return 0
    return Math.round((status.value.current / status.value.total) * 100)
})

const addLog = (msg) => {
    const time = new Date().toLocaleTimeString('zh-CN')
    logs.value.push(`[${time}] ${msg}`)
    if (logs.value.length > 200) {
        logs.value = logs.value.slice(-200)
    }
}

const loadConfig = () => {
    loading.value = true
    return LoadConfig().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200 && resp.data) {
            config.value = {
                adb_path: typeof resp.data.adb_path === 'string' ? resp.data.adb_path : defaultConfig.adb_path,
                adb_serial: typeof resp.data.adb_serial === 'string' ? resp.data.adb_serial : defaultConfig.adb_serial,
                scroll_count: typeof resp.data.scroll_count === 'number' ? resp.data.scroll_count : defaultConfig.scroll_count,
                scroll_delay: typeof resp.data.scroll_delay === 'number' ? resp.data.scroll_delay : defaultConfig.scroll_delay,
                scroll_duration: typeof resp.data.scroll_duration === 'number' ? resp.data.scroll_duration : defaultConfig.scroll_duration
            }
            addLog('配置已加载')
        } else {
            addLog('配置加载失败，使用默认值')
        }
    }).catch(e => {
        addLog('加载配置失败: ' + e)
    }).finally(() => {
        loading.value = false
    })
}

const saveConfig = () => {
    SaveConfig(JSON.stringify(config.value)).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            nmessage.success('配置已保存')
            addLog('配置已保存')
        } else {
            nmessage.error(resp.msg)
            addLog('保存配置失败: ' + resp.msg)
        }
    }).catch(e => {
        nmessage.error('保存失败: ' + e)
        addLog('保存配置失败: ' + e)
    })
}

const checkConnection = () => {
    checking.value = true
    addLog('检查ADB连接...')
    CheckAdbConnection(JSON.stringify({
        adb_path: config.value.adb_path || '',
        adb_serial: config.value.adb_serial || ''
    })).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200 && resp.data.connected) {
            adbConnected.value = true
            screenSize.value = resp.data.screen
            nmessage.success('ADB已连接: ' + resp.data.screen)
            addLog('ADB已连接: ' + resp.data.screen)
            fetchStatus()
        } else {
            adbConnected.value = false
            screenSize.value = '未知'
            const msg = resp.data?.message || '连接失败'
            nmessage.warning(msg)
            addLog('ADB未连接: ' + msg)
        }
    }).catch(e => {
        adbConnected.value = false
        nmessage.error('检查失败: ' + e)
        addLog('检查ADB失败: ' + e)
    }).finally(() => {
        checking.value = false
    })
}

const fetchStatus = () => {
    GetAutoScrollStatus().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200 && resp.data) {
            status.value = resp.data
            if (status.value.running && status.value.current > 0) {
                if (status.value.current === 1) {
                    addLog(`开始翻页: ${status.value.total}次`)
                }
            }
        }
    }).catch(() => {})
}

const startScroll = () => {
    if (!adbConnected.value) {
        nmessage.warning('请先检查ADB连接')
        addLog('请先检查ADB连接')
        return
    }

    starting.value = true
    addLog(`开始自动翻页: ${config.value.scroll_count}次, 间隔${config.value.scroll_delay}ms`)

    StartAutoScroll(JSON.stringify({
        adb_path: config.value.adb_path || '',
        adb_serial: config.value.adb_serial || '',
        count: Number(config.value.scroll_count) || 5000,
        delay: Number(config.value.scroll_delay) || 100,
        duration: Number(config.value.scroll_duration) || 100
    })).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            nmessage.success(resp.msg)
            addLog(resp.msg)
            startPolling()
        } else {
            nmessage.error(resp.msg)
            addLog('启动失败: ' + resp.msg)
        }
    }).catch(e => {
        nmessage.error('启动失败: ' + e)
        addLog('启动失败: ' + e)
    }).finally(() => {
        starting.value = false
    })
}

const stopScroll = () => {
    StopAutoScroll().then(v => {
        let resp = JSON.parse(v)
        nmessage.info(resp.msg)
        addLog(resp.msg)
        stopPolling()
        fetchStatus()
    }).catch(e => {
        nmessage.error('停止失败: ' + e)
        addLog('停止失败: ' + e)
    })
}

const startPolling = () => {
    stopPolling()
    statusTimer = setInterval(() => {
        fetchStatus()
    }, 1000)
}

const stopPolling = () => {
    if (statusTimer) {
        clearInterval(statusTimer)
        statusTimer = null
    }
}

const clearLogs = () => {
    logs.value = []
    addLog('日志已清空')
}

onMounted(async () => {
    await loadConfig()
    checkConnection()
})

onUnmounted(() => {
    stopPolling()
})
</script>

<template>
    <div class="autoscroll-page">
        <div class="page-header">
            <h1 class="page-title">
                <RefreshCw :size="24" />
                自动翻页助手
            </h1>
            <p class="page-desc">自动滑动游戏战报页面，配合抓包工具采集数据</p>
        </div>

        <div class="page-content">
            <div class="main-grid">
                <div class="left-column">
                    <n-card title="ADB 配置" class="config-card">
                        <div class="form-group">
                            <label class="form-label">ADB 路径</label>
                            <n-input
                                v-model:value="config.adb_path"
                                placeholder="如: C:\adb\adb.exe"
                                :disabled="status.running"
                            />
                        </div>
                        <div class="form-group">
                            <label class="form-label">ADB Serial</label>
                            <n-input
                                v-model:value="config.adb_serial"
                                placeholder="如: 127.0.0.1:16384"
                                :disabled="status.running"
                            />
                        </div>
                        <div class="form-group">
                            <label class="form-label">连接状态</label>
                            <div class="connection-status">
                                <n-tag v-if="adbConnected" type="success">
                                    <template #icon><Wifi :size="14" /></template>
                                    已连接
                                </n-tag>
                                <n-tag v-else type="error">
                                    <template #icon><WifiOff :size="14" /></template>
                                    未连接
                                </n-tag>
                                <span class="screen-info" v-if="adbConnected">
                                    <Monitor :size="14" />
                                    {{ screenSize }}
                                </span>
                            </div>
                        </div>
                        <div class="form-actions">
                            <n-button @click="checkConnection" :loading="checking" :disabled="status.running">
                                检查连接
                            </n-button>
                            <n-button type="primary" @click="saveConfig" :disabled="status.running">
                                <template #icon><Save :size="14" /></template>
                                保存配置
                            </n-button>
                        </div>
                    </n-card>

                    <n-card title="翻页配置" class="config-card">
                        <div class="config-row">
                            <div class="form-group">
                                <label class="form-label">滑动次数</label>
                                <n-input-number
                                    v-model:value="config.scroll_count"
                                    :min="1"
                                    :max="50000"
                                    :disabled="status.running"
                                    style="width: 120px"
                                />
                            </div>
                            <div class="form-group">
                                <label class="form-label">间隔(ms)</label>
                                <n-input-number
                                    v-model:value="config.scroll_delay"
                                    :min="50"
                                    :max="5000"
                                    :disabled="status.running"
                                    style="width: 100px"
                                />
                            </div>
                            <div class="form-group">
                                <label class="form-label">时长(ms)</label>
                                <n-input-number
                                    v-model:value="config.scroll_duration"
                                    :min="50"
                                    :max="1000"
                                    :disabled="status.running"
                                    style="width: 100px"
                                />
                            </div>
                        </div>
                    </n-card>

                    <n-card title="状态与控制" class="config-card">
                        <div class="status-section">
                            <div class="status-row">
                                <n-tag v-if="status.running" type="success" size="large">
                                    运行中
                                </n-tag>
                                <n-tag v-else type="default" size="large">
                                    已停止
                                </n-tag>
                                <span class="status-text" v-if="status.running">
                                    {{ status.current }} / {{ status.total }} 次
                                </span>
                            </div>
                            <n-progress
                                v-if="status.running"
                                type="line"
                                :percentage="progressPercent"
                                :indicator-placement="'inside'"
                            />
                        </div>
                        <div class="control-buttons">
                            <n-button
                                v-if="!status.running"
                                type="primary"
                                size="large"
                                @click="startScroll"
                                :loading="starting"
                                :disabled="!adbConnected"
                            >
                                <template #icon><Play :size="16" /></template>
                                开始翻页
                            </n-button>
                            <n-button
                                v-else
                                type="error"
                                size="large"
                                @click="stopScroll"
                            >
                                <template #icon><Square :size="16" /></template>
                                停止
                            </n-button>
                        </div>
                        <n-alert v-if="!adbConnected" type="warning" :show-icon="true">
                            请先检查ADB连接，确保模拟器已开启
                        </n-alert>
                    </n-card>
                </div>

                <div class="right-column">
                    <n-card title="运行日志" class="log-card">
                        <template #header-extra>
                            <n-button size="small" @click="clearLogs">清空</n-button>
                        </template>
                        <div class="log-container">
                            <div v-if="logs.length === 0" class="log-empty">
                                <n-empty description="暂无日志" />
                            </div>
                            <div v-else class="log-list">
                                <div v-for="(log, i) in logs" :key="i" class="log-item">
                                    {{ log }}
                                </div>
                            </div>
                        </div>
                    </n-card>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
.autoscroll-page {
    max-width: 1200px;
    margin: 0 auto;
}

.page-header {
    margin-bottom: 24px;
    .page-title {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 22px;
        font-weight: 600;
        color: var(--color-text);
        margin: 0 0 8px;
    }
    .page-desc {
        font-size: 14px;
        color: var(--color-text-secondary);
        margin: 0;
    }
}

.main-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.left-column {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.right-column {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.config-card {
    :deep(.n-card__content) {
        padding: 16px;
    }
}

.form-group {
    margin-bottom: 16px;
    &:last-child {
        margin-bottom: 0;
    }
}

.form-label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text);
    margin-bottom: 6px;
}

.connection-status {
    display: flex;
    align-items: center;
    gap: 12px;
    .screen-info {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: var(--color-text-secondary);
    }
}

.form-actions {
    display: flex;
    gap: 12px;
    margin-top: 16px;
}

.config-row {
    display: flex;
    gap: 20px;
    .form-group {
        flex: 1;
    }
}

.status-section {
    margin-bottom: 20px;
    .status-row {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
        .status-text {
            font-size: 14px;
            color: var(--color-text-secondary);
        }
    }
}

.control-buttons {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-bottom: 16px;
}

.log-card {
    height: 500px;
    display: flex;
    flex-direction: column;
    :deep(.n-card__content) {
        flex: 1;
        overflow: hidden;
        padding: 0 !important;
    }
}

.log-container {
    height: 100%;
    overflow: hidden;
    .log-empty {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
    }
    .log-list {
        height: 100%;
        overflow-y: auto;
        padding: 12px;
        font-family: monospace;
        font-size: 12px;
        line-height: 1.8;
        .log-item {
            color: var(--color-text);
            word-break: break-all;
        }
    }
}
</style>