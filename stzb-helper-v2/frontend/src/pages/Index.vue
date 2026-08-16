<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { NCard, NButton, NSpace, NAlert, useMessage, NTag, NInputNumber, NSwitch, NSelect } from 'naive-ui'
import { EnableGetBattleReport, DisableGetBattleReport, GetTaskList, GetTeamUser, CheckUpdate, GetVersion, GetGroupWu, GetDbList, GetAutoScrollStatus, StartAutoScroll, StopAutoScroll, CheckAdbConnection, AutoConnectDb, GetCaptureModeStatus, LoadConfig, SetActiveAdbProfile } from '../../wailsjs/go/main/App'
import { BrowserOpenURL } from '../../wailsjs/runtime/runtime'
import { RefreshCw, Users, Swords, ClipboardList, BarChart3, BookOpen, Search, TrendingUp, Trophy, Smartphone } from 'lucide-vue-next'

const nmessage = useMessage()

const taskCount = ref(0)
const memberCount = ref(0)
const groupCount = ref(0)
const version = ref('')
const updateInfo = ref(null)
const checkingUpdate = ref(false)
const battleCount = ref(0)
const dbName = ref('')
const groupWuData = ref([])
const recentMembers = ref([])
const captureMode = ref({ mode: 'none', running: false, report_pos: 0, message: '当前未开启战报采集' })
const appConfig = ref<any>({ adb_profiles: [], active_adb_profile_id: '', adb_path: '', adb_serial: '' })

const autoScrollStatus = ref({
    running: false,
    current: 0,
    total: 0,
    screen_width: 1080,
    screen_height: 1920,
    stop_reason: '',
    duplicate_found: false,
    stop_on_duplicate: false,
    inserted_count: 0,
    duplicate_count: 0,
    last_battle_id: 0,
    active_database_path: '',
})
const scrollCount = ref(8000)
const scrollDelay = ref(100)
const scrollDuration = ref(100)
const scrollStopOnDuplicate = ref(false)
const adbConnected = ref(false)
const pageLoading = ref(true)
let statusTimer = null

const ensureArray = (value) => Array.isArray(value) ? value : []
const getPathBasename = (path: string) => {
    if (!path) return ''
    const parts = path.split(/[\\/]/)
    return parts[parts.length - 1] || path
}
const activeAdbOptions = computed(() => ensureArray(appConfig.value.adb_profiles).map((profile: any) => ({
    label: `${profile.name} (${profile.adb_serial})`,
    value: profile.id,
})))
const currentAdbProfile = computed(() => ensureArray(appConfig.value.adb_profiles).find((profile: any) => profile.id === appConfig.value.active_adb_profile_id) || null)
const activeDatabaseName = computed(() => getPathBasename(autoScrollStatus.value.active_database_path || dbName.value))
const duplicateStrategyLabel = computed(() => autoScrollStatus.value.stop_on_duplicate ? '发现重复后停止' : '发现重复后继续')

const statCards = computed(() => [
    { label: '同盟成员', value: memberCount.value, icon: Users, color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.12)' },
    { label: '攻城任务', value: taskCount.value, icon: ClipboardList, color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)' },
    { label: '分组数量', value: groupCount.value, icon: Swords, color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' },
    { label: '战报数据', value: battleCount.value, icon: BarChart3, color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.12)' },
])

const quickActions = [
    { label: '队伍查询', icon: Search, path: '/teamquery', desc: '查询玩家队伍' },
    { label: '队伍胜率', icon: BarChart3, path: '/teamwinrate', desc: '队伍胜率统计' },
    { label: '分组武勋', icon: Trophy, path: '/groupWu', desc: '分组武勋排行' },
    { label: '同盟成员', icon: Users, path: '/teamuser', desc: '成员列表' },
    { label: '主公簿', icon: BookOpen, path: '/book', desc: '玩家数据' },
    { label: '攻城任务', icon: ClipboardList, path: '/task', desc: '考勤管理' },
]

const topGroups = computed(() => {
    return [...groupWuData.value]
        .sort((a, b) => b.total_wu - a.total_wu)
        .slice(0, 5)
})

const avgWu = computed(() => {
    if (!groupWuData.value.length) return 0
    const total = groupWuData.value.reduce((sum, g) => sum + g.average_wu, 0)
    return Math.round(total / groupWuData.value.length)
})

const onCheckUpdate = () => {
    checkingUpdate.value = true
    updateInfo.value = null
    CheckUpdate().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) updateInfo.value = resp.data
    }).catch(e => nmessage.error('检查更新失败: ' + e))
    .finally(() => checkingUpdate.value = false)
}

const openUpdateUrl = (url) => BrowserOpenURL(url)

const refreshCaptureMode = () => {
    GetCaptureModeStatus().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) captureMode.value = resp.data
    }).catch(() => {})
}

const onEnableGetBattleReport = () => {
    EnableGetBattleReport().then(v => {
        let data = JSON.parse(v)
        if (data.code == 200) {
            captureMode.value = data.data
            nmessage.success(data.msg)
        } else {
            nmessage.error(data.msg)
        }
    }).catch(e => nmessage.error('开启失败: ' + e))
}

const onDisableGetBattleReport = () => {
    DisableGetBattleReport().then(v => {
        let data = JSON.parse(v)
        if (data.code == 200) {
            captureMode.value = data.data
            nmessage.info(data.msg)
        } else {
            nmessage.error(data.msg)
        }
    }).catch(e => nmessage.error('关闭失败: ' + e))
}

const fetchAutoScrollStatus = (syncPolling = false) => {
    GetAutoScrollStatus().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            autoScrollStatus.value = resp.data
            if (syncPolling) {
                if (resp.data.running) {
                    startStatusPolling()
                } else {
                    stopStatusPolling()
                }
            }
        }
    }).catch(() => {})
}

const loadAdbConfig = () => {
    LoadConfig().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200 && resp.data) {
            appConfig.value = resp.data
            scrollCount.value = resp.data.scroll_count || scrollCount.value
            scrollDelay.value = resp.data.scroll_delay || scrollDelay.value
            scrollDuration.value = resp.data.scroll_duration || scrollDuration.value
            scrollStopOnDuplicate.value = typeof resp.data.stop_on_duplicate === 'boolean' ? resp.data.stop_on_duplicate : scrollStopOnDuplicate.value
        }
    }).catch(() => {})
}

const onStartAutoScroll = () => {
    if (!adbConnected.value) {
        nmessage.warning('ADB未连接，请先检查连接')
        return
    }
    StartAutoScroll(JSON.stringify({adb_path: '', adb_serial: '', count: scrollCount.value, delay: scrollDelay.value, duration: scrollDuration.value, stop_on_duplicate: scrollStopOnDuplicate.value})).then(v => {
        let data = JSON.parse(v)
        if (data.code == 200) {
            nmessage.success(data.msg)
            startStatusPolling()
            fetchAutoScrollStatus()
        } else {
            nmessage.error(data.msg)
        }
    }).catch(e => nmessage.error('停止失败: ' + e))
}

const onStopAutoScroll = () => {
    StopAutoScroll().then(v => {
        let data = JSON.parse(v)
        nmessage.info(data.msg)
        stopStatusPolling()
        fetchAutoScrollStatus()
    }).catch(e => nmessage.error('停止失败: ' + e))
}

const onCheckAdb = () => {
    CheckAdbConnection('').then(v => {
        let data = JSON.parse(v)
        if (data.code == 200 && data.data.connected) {
            adbConnected.value = true
            nmessage.success('ADB已连接: ' + data.data.screen)
            fetchAutoScrollStatus()
        } else {
            adbConnected.value = false
            nmessage.error(data.msg || 'ADB未连接')
        }
    }).catch(e => {
        adbConnected.value = false
        nmessage.error('检查ADB失败: ' + e)
    })
}

const onChangeActiveAdbProfile = (profileId: string) => {
    if (autoScrollStatus.value.running) {
        nmessage.warning('自动翻页运行中，不能切换模拟器实例')
        return
    }
    SetActiveAdbProfile(profileId).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            appConfig.value.active_adb_profile_id = profileId
            nmessage.success(resp.msg)
            onCheckAdb()
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('切换模拟器实例失败: ' + e)
    })
}

const startStatusPolling = () => {
    stopStatusPolling()
    statusTimer = setInterval(() => {
        fetchAutoScrollStatus()
    }, 1000)
}

const stopStatusPolling = () => {
    if (statusTimer) {
        clearInterval(statusTimer)
        statusTimer = null
    }
}

onMounted(async () => {
    // Auto-connect to configured database
    await AutoConnectDb().then(v => {
        let resp = JSON.parse(v)
        if (resp.code != 200) {
            console.log('Auto-connect failed:', resp.msg)
        }
    }).catch(() => {})

    await Promise.allSettled([
        GetVersion().then(v => {
            let resp = JSON.parse(v)
            if (resp.code == 200) version.value = resp.data
        }),
        GetTaskList().then(v => {
            let resp = JSON.parse(v)
            if (resp.code == 200) taskCount.value = ensureArray(resp.data).length
        }),
        GetTeamUser().then(v => {
            let data = JSON.parse(v)
            if (data.code == 200) {
                const rows = ensureArray(data.data)
                memberCount.value = rows.length
                recentMembers.value = rows.slice(0, 5)
                battleCount.value = rows.length * 3 // 估算
            }
        }),
        GetGroupWu().then(v => {
            let resp = JSON.parse(v)
            if (resp.code == 200) {
                const rows = ensureArray(resp.data)
                groupWuData.value = rows
                battleCount.value = rows.reduce((sum, g) => sum + g.member_count * 2, 0) // 估算
            }
        }),
        GetDbList().then(v => {
            let resp = JSON.parse(v)
            const rows = ensureArray(resp.data)
            if (resp.code == 200 && rows.length > 0) dbName.value = rows[0]
        }),
    ]).finally(() => {
        pageLoading.value = false
    })

    loadAdbConfig()
    refreshCaptureMode()
    onCheckAdb()
    fetchAutoScrollStatus(true)
})
</script>

<template>
    <div class="dashboard">
        <div class="dashboard-header">
            <div class="header-left">
                        <h1 class="title">数据概览</h1>
                        <p class="subtitle">{{ dbName || '未选择数据库' }}</p>
                    </div>
            <n-space align="center">
                <router-link to="/select-db" class="db-manage-link">管理数据库</router-link>
                <n-tag type="info">v{{ version }}</n-tag>
            </n-space>
        </div>

        <div class="stat-grid" v-if="!pageLoading">
            <div class="stat-card" v-for="stat in statCards" :key="stat.label">
                <div class="stat-icon" :style="{ background: stat.bg, color: stat.color }">
                    <component :is="stat.icon" :size="20" />
                </div>
                <div class="stat-info">
                    <span class="stat-value">{{ stat.value }}</span>
                    <span class="stat-label">{{ stat.label }}</span>
                </div>
            </div>
        </div>
        <div class="stat-grid" v-else>
            <div class="stat-card stat-card--loading" v-for="i in 4" :key="i">
                <div class="skeleton skeleton-icon"></div>
                <div class="stat-info">
                    <div class="skeleton skeleton-line" style="width: 60px;"></div>
                    <div class="skeleton skeleton-line" style="width: 80px;"></div>
                </div>
            </div>
        </div>

        <div class="main-grid">
            <div class="left-col">
                <div class="section card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <Trophy :size="16" />
                            分组武勋排行
                        </h3>
                    </div>
                    <div class="wu-list" v-if="topGroups.length">
                        <div class="wu-item" v-for="(group, i) in topGroups" :key="group.group">
                            <span class="wu-rank" :class="{ top: i < 3 }">{{ i + 1 }}</span>
                            <div class="wu-info">
                                <span class="wu-name">{{ group.group }}</span>
                                <span class="wu-meta">{{ group.member_count }}人</span>
                            </div>
                            <div class="wu-stats">
                                <span class="wu-total">{{ group.total_wu }} 武勋</span>
                                <span class="wu-avg">人均 {{ Math.round(group.average_wu) }}</span>
                            </div>
                        </div>
                    </div>
                    <div v-else class="empty-tip">暂无数据</div>
                </div>

                <div class="section card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <TrendingUp :size="16" />
                            数据趋势
                        </h3>
                    </div>
                    <div class="trend-stats">
                        <div class="trend-item">
                            <span class="trend-label">人均武勋</span>
                            <span class="trend-value">{{ avgWu }}</span>
                        </div>
                        <div class="trend-item">
                            <span class="trend-label">0武勋成员</span>
                            <span class="trend-value warn">
                                {{ groupWuData.find(g => g.zero_wu_count)?.zero_wu_count || 0 }}
                            </span>
                        </div>
                        <div class="trend-item">
                            <span class="trend-label">活跃分组</span>
                            <span class="trend-value">{{ groupWuData.filter(g => g.average_wu > 0).length }}</span>
                        </div>
                    </div>
                </div>

                <div class="section card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <Search :size="16" />
                            快捷入口
                        </h3>
                    </div>
                    <div class="quick-grid">
                        <router-link :to="action.path" class="quick-item" v-for="action in quickActions" :key="action.path">
                            <div class="quick-icon">
                                <component :is="action.icon" :size="18" />
                            </div>
                            <div class="quick-info">
                                <span class="quick-label">{{ action.label }}</span>
                                <span class="quick-desc">{{ action.desc }}</span>
                            </div>
                        </router-link>
                    </div>
                </div>
            </div>

            <div class="right-col">
                <div class="section card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <ClipboardList :size="16" />
                            战报采集
                        </h3>
                    </div>
                    <div class="capture-tip">
                        <div class="tip-text">
                            <span class="tip-label">当前模式：{{ captureMode.mode === 'attendance_report' ? '考勤守军' : captureMode.mode === 'battle_detail' ? '详细战报' : '未开启' }}</span>
                            <span class="tip-desc">{{ captureMode.message }}</span>
                            <span class="tip-desc">详细战报和考勤守军都需要手动主动开启；不主动开启时会跳过解析</span>
                            <span class="tip-desc" v-if="captureMode.mode === 'attendance_report'">考勤模式已开启，可在攻城任务弹窗里持续采集，除非你手动停止</span>
                        </div>
                        <n-space vertical align="end" size="small">
                            <n-tag :type="captureMode.mode === 'attendance_report' ? 'success' : captureMode.mode === 'battle_detail' ? 'warning' : 'default'" :bordered="false">
                                {{ captureMode.running ? '采集中' : '已停止' }}
                            </n-tag>
                            <n-button type="primary" size="small" @click="onEnableGetBattleReport">开启</n-button>
                            <n-button size="small" @click="onDisableGetBattleReport">停止</n-button>
                        </n-space>
                    </div>
                </div>

                <div class="section card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <RefreshCw :size="16" />
                            自动翻页
                        </h3>
                    </div>
                    <div class="auto-scroll-panel">
                        <div class="scroll-status">
                            <n-tag v-if="adbConnected" type="success">ADB已连接</n-tag>
                            <n-tag v-else type="warning">ADB未连接</n-tag>
                            <n-tag v-if="autoScrollStatus.running" type="info">运行中 {{ autoScrollStatus.current }}/{{ autoScrollStatus.total }}</n-tag>
                            <n-tag v-else type="default">已停止</n-tag>
                        </div>
                        <div class="adb-profile-panel">
                            <div class="config-item profile-select-item">
                                <span class="config-label">当前实例</span>
                                <n-select
                                    :value="appConfig.active_adb_profile_id"
                                    :options="activeAdbOptions"
                                    placeholder="请选择模拟器实例"
                                    size="small"
                                    style="width: 260px"
                                    :disabled="autoScrollStatus.running"
                                    @update:value="onChangeActiveAdbProfile"
                                />
                            </div>
                            <div class="profile-meta" v-if="currentAdbProfile">
                                <Smartphone :size="14" />
                                <span>{{ currentAdbProfile.adb_serial }}</span>
                            </div>
                        </div>
                        <div class="scroll-config">
                            <div class="config-item">
                                <span class="config-label">滑动次数</span>
                                <n-input-number v-model:value="scrollCount" :min="1" :max="50000" size="small" style="width: 140px" :disabled="autoScrollStatus.running" />
                            </div>
                            <div class="config-item">
                                <span class="config-label">间隔(ms)</span>
                                <n-input-number v-model:value="scrollDelay" :min="50" :max="5000" size="small" style="width: 130px" :disabled="autoScrollStatus.running" />
                            </div>
                            <div class="config-item">
                                <span class="config-label">时长(ms)</span>
                                <n-input-number v-model:value="scrollDuration" :min="50" :max="1000" size="small" style="width: 120px" :disabled="autoScrollStatus.running" />
                            </div>
                            <div class="config-item duplicate-config">
                                <span class="config-label">重复自动停</span>
                                <n-switch v-model:value="scrollStopOnDuplicate" size="small" :disabled="autoScrollStatus.running" />
                            </div>
                        </div>
                        <div class="scroll-screen">
                            <span class="screen-info">屏幕: {{ autoScrollStatus.screen_width }}x{{ autoScrollStatus.screen_height }}</span>
                        </div>
                        <div class="scroll-summary">
                            <div class="summary-row">
                                <span class="summary-label">当前写入数据库</span>
                                <span class="summary-value">{{ activeDatabaseName || '未连接数据库' }}</span>
                            </div>
                            <div v-if="autoScrollStatus.active_database_path" class="summary-path">{{ autoScrollStatus.active_database_path }}</div>
                            <div class="summary-row">
                                <span class="summary-label">重复策略</span>
                                <span class="summary-value">{{ duplicateStrategyLabel }}</span>
                            </div>
                            <div class="summary-grid">
                                <div class="summary-metric">
                                    <span class="metric-label">新增战报</span>
                                    <strong>{{ autoScrollStatus.inserted_count }}</strong>
                                </div>
                                <div class="summary-metric">
                                    <span class="metric-label">重复战报</span>
                                    <strong>{{ autoScrollStatus.duplicate_count }}</strong>
                                </div>
                                <div class="summary-metric">
                                    <span class="metric-label">最后 battle_id</span>
                                    <strong>{{ autoScrollStatus.last_battle_id || '-' }}</strong>
                                </div>
                            </div>
                        </div>
                        <div v-if="!autoScrollStatus.running && autoScrollStatus.stop_reason" class="scroll-reason">
                            {{ autoScrollStatus.stop_reason }}
                        </div>
                        <n-space>
                            <n-button size="small" @click="onCheckAdb" :disabled="autoScrollStatus.running">
                                检查连接
                            </n-button>
                            <n-button v-if="!autoScrollStatus.running" type="primary" size="small" @click="onStartAutoScroll">
                                开始翻页
                            </n-button>
                            <n-button v-else type="error" size="small" @click="onStopAutoScroll">
                                停止
                            </n-button>
                        </n-space>
                    </div>
                </div>
            </div>
        </div>

        <n-alert v-if="updateInfo && updateInfo.hasUpdate" type="success" :show-icon="false" class="update-alert">
            <div class="update-content">
                <div>
                    <strong>新版本 {{ updateInfo.latestVer }}</strong>
                    <p class="update-body">{{ updateInfo.body?.slice(0, 80) }}...</p>
                </div>
                <n-button type="primary" size="small" @click="openUpdateUrl(updateInfo.url)">更新</n-button>
            </div>
        </n-alert>
    </div>
</template>

<style scoped lang="scss">
.dashboard {
    max-width: 1100px;
    margin: 0 auto;
}

.dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .title { font-size: 20px; font-weight: 600; margin: 0; }
    .subtitle { font-size: 13px; color: #999; margin: 4px 0 0; }
}

.db-manage-link {
    font-size: 13px;
    color: var(--color-accent);
    text-decoration: none;
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}

.stat-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    background: var(--color-surface);
    border-radius: 10px;
    border: 1px solid var(--color-border-light);

    &.stat-card--loading {
        border-color: var(--color-border-light);
    }

    .stat-icon {
        width: 40px; height: 40px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .stat-info { display: flex; flex-direction: column; }
    .stat-value { font-size: 20px; font-weight: 600; color: var(--color-text); }
    .stat-label { font-size: 12px; color: var(--color-text-secondary); }
}

.skeleton {
    border-radius: 6px;
    background: var(--color-border);
    animation: skeleton-pulse 1.2s ease-in-out infinite;
}

.skeleton-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    flex-shrink: 0;
}

.skeleton-line {
    height: 12px;
    margin-bottom: 6px;

    &:last-child { margin-bottom: 0; }
}

@keyframes skeleton-pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
}

.main-grid {
    display: grid;
    grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
    gap: 16px;
    align-items: start;
}

.left-col, .right-col {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.card {
    background: var(--color-surface);
    border-radius: 10px;
    border: 1px solid var(--color-border-light);
    padding: 16px;
}

.section-header {
    margin-bottom: 14px;
    .section-title {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 14px;
        font-weight: 600;
        color: var(--color-text);
        margin: 0;
    }
}

.wu-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.wu-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    background: var(--color-surface-hover);
    border-radius: 8px;

    .wu-rank {
        width: 22px; height: 22px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        background: var(--color-border);
        font-size: 12px;
        font-weight: 600;
        color: var(--color-text-secondary);
        &.top { background: #fef3c7; color: #d97706; }
    }

    .wu-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        .wu-name { font-size: 13px; font-weight: 500; }
        .wu-meta { font-size: 11px; color: #999; }
    }

    .wu-stats {
        text-align: right;
        .wu-total { font-size: 13px; font-weight: 600; color: #f59e0b; }
        .wu-avg { font-size: 11px; color: #999; display: block; }
    }
}

.trend-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;

    .trend-item {
        text-align: center;
        padding: 12px;
        background: var(--color-surface-hover);
        border-radius: 8px;

        .trend-label { font-size: 12px; color: var(--color-text-secondary); display: block; margin-bottom: 4px; }
        .trend-value { font-size: 20px; font-weight: 600; color: var(--color-text); }
        .trend-value.warn { color: #ef4444; }
    }
}

.quick-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
}

.quick-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: var(--color-surface-hover);
    border-radius: 8px;
    text-decoration: none;
    color: inherit;
    transition: all 0.2s;

    &:hover { background: var(--color-primary-light); }

    .quick-icon {
        width: 32px; height: 32px;
        border-radius: 6px;
        background: var(--color-surface);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--color-text-secondary);
    }

    .quick-info {
        display: flex;
        flex-direction: column;
        .quick-label { font-size: 13px; font-weight: 500; }
        .quick-desc { font-size: 11px; color: var(--color-text-secondary); }
    }
}

.capture-tip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px;
    background: var(--color-primary-light);
    border-radius: 8px;

    .tip-text { display: flex; flex-direction: column; }
    .tip-label { font-size: 13px; font-weight: 500; }
    .tip-desc { font-size: 11px; color: var(--color-text-secondary); }
}

.auto-scroll-panel {
    padding: 12px;
    background: var(--color-primary-light);
    border-radius: 8px;

    .scroll-status {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
        .status-text { font-size: 13px; color: #666; }
    }

    .scroll-config {
        display: flex;
        gap: 16px;
        margin-bottom: 12px;
        .config-item {
            display: flex;
            align-items: center;
            gap: 6px;
            .config-label { font-size: 12px; color: #666; }
        }
        .duplicate-config {
            padding: 0 8px;
            min-height: 28px;
            border: 1px solid var(--color-border-light);
            border-radius: 8px;
            background: var(--color-surface-hover);
        }
    }

    .adb-profile-panel {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
        flex-wrap: wrap;
    }

    .profile-select-item {
        align-items: center;
    }

    .profile-meta {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--color-text-secondary);
    }

    .scroll-screen {
        margin-bottom: 12px;
        .screen-info { font-size: 11px; color: #999; }
    }

    .scroll-summary {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 12px;
        padding: 10px 12px;
        background: var(--color-surface-hover);
        border: 1px solid var(--color-border);
        border-radius: 10px;
    }

    .summary-row {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        font-size: 13px;
    }

    .summary-label {
        color: var(--color-text-secondary);
    }

    .summary-value {
        color: var(--color-text);
        font-weight: 600;
        text-align: right;
    }

    .summary-path {
        font-size: 12px;
        color: var(--color-text-secondary);
        word-break: break-all;
    }

    .summary-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
    }

    .summary-metric {
        padding: 10px;
        background: var(--color-surface);
        border-radius: 8px;
        border: 1px solid var(--color-border);
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .metric-label {
        font-size: 12px;
        color: var(--color-text-secondary);
    }

    .scroll-reason {
        margin-bottom: 12px;
        padding: 8px 10px;
        border: 1px solid var(--color-border-light);
        border-radius: 8px;
        background: var(--color-surface-hover);
        color: var(--color-text);
        font-size: 12px;
        line-height: 1.5;
    }
}

.update-alert {
    margin-top: 16px; border-radius: 10px;
    .update-content { display: flex; justify-content: space-between; align-items: center; }
    .update-body { font-size: 12px; color: #666; margin: 4px 0 0; }
}

.empty-tip {
    text-align: center;
    padding: 20px;
    color: #999;
    font-size: 13px;
}

@media (max-width: 768px) {
    .stat-grid { grid-template-columns: repeat(2, 1fr) !important; }
    .main-grid { grid-template-columns: 1fr !important; }
}
</style>
