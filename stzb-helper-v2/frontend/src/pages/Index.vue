<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { NCard, NButton, NStatistic, NSpace, NGrid, NGi, NAlert, NSpin, useMessage, NTag, NEmpty, NProgress, NInputNumber } from 'naive-ui'
import { EnableGetBattleReport, DisableGetBattleReport, GetTaskList, GetTeamUser, CheckUpdate, GetVersion, GetGroupWu, GetDbList, GetAutoScrollStatus, StartAutoScroll, StopAutoScroll, CheckAdbConnection, AutoConnectDb } from '../../wailsjs/go/main/App'
import { BrowserOpenURL } from '../../wailsjs/runtime/runtime'
import { RefreshCw, Download, Users, Swords, ClipboardList, BarChart3, BookOpen, Search, TrendingUp, Trophy, Clock } from 'lucide-vue-next'

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

const autoScrollStatus = ref({ running: false, current: 0, total: 0, screen_width: 1080, screen_height: 1920 })
const scrollCount = ref(8000)
const scrollDelay = ref(100)
const scrollDuration = ref(100)
const adbConnected = ref(false)
let statusTimer = null

const statCards = computed(() => [
    { label: '同盟成员', value: memberCount.value, icon: Users, color: '#3b82f6', bg: '#eff6ff' },
    { label: '攻城任务', value: taskCount.value, icon: ClipboardList, color: '#f59e0b', bg: '#fffbeb' },
    { label: '分组数量', value: groupCount.value, icon: Swords, color: '#10b981', bg: '#ecfdf5' },
    { label: '战报数据', value: battleCount.value, icon: BarChart3, color: '#8b5cf6', bg: '#f5f3ff' },
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

const onEnableGetBattleReport = () => {
    EnableGetBattleReport().then(v => {
        let data = JSON.parse(v)
        data.code == 200 ? nmessage.success('已开启详细战报获取') : nmessage.error(data.msg)
    }).catch(e => nmessage.error('开启失败: ' + e))
}

const onDisableGetBattleReport = () => {
    DisableGetBattleReport().then(v => {
        let data = JSON.parse(v)
        data.code == 200 ? nmessage.success('已关闭') : nmessage.error(data.msg)
    }).catch(e => nmessage.error('关闭失败: ' + e))
}

const fetchAutoScrollStatus = () => {
    GetAutoScrollStatus().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) autoScrollStatus.value = resp.data
    }).catch(() => {})
}

const onStartAutoScroll = () => {
    if (!adbConnected.value) {
        nmessage.warning('ADB未连接，请先检查连接')
        return
    }
    StartAutoScroll(JSON.stringify({adb_path: '', adb_serial: '', count: scrollCount.value, delay: scrollDelay.value, duration: scrollDuration.value})).then(v => {
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

onMounted(() => {
    // Auto-connect to configured database
    AutoConnectDb().then(v => {
        let resp = JSON.parse(v)
        if (resp.code != 200) {
            console.log('Auto-connect failed:', resp.msg)
        }
    }).catch(() => {})

    GetVersion().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) version.value = resp.data
    }).catch(() => {})

    GetTaskList().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) taskCount.value = resp.data.length
    }).catch(() => {})

    GetTeamUser().then(v => {
        let data = JSON.parse(v)
        if (data.data) {
            memberCount.value = data.data.length
            recentMembers.value = data.data.slice(0, 5)
            battleCount.value = data.data.length * 3 // 估算
        }
    }).catch(() => {})

    GetGroupWu().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            groupWuData.value = resp.data
            battleCount.value = resp.data.reduce((sum, g) => sum + g.member_count * 2, 0) // 估算
        }
    }).catch(() => {})

    GetDbList().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200 && resp.data.length > 0) dbName.value = resp.data[0]
    }).catch(() => {})

    onCheckAdb()
})
</script>

<template>
    <div class="dashboard">
        <div class="dashboard-header">
            <div class="header-left">
                <h1 class="title">数据概览</h1>
                <p class="subtitle">{{ dbName || '未选择数据库' }}</p>
            </div>
            <n-tag type="info">v{{ version }}</n-tag>
        </div>

        <div class="stat-grid">
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
            </div>

            <div class="right-col">
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

                <div class="section card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <ClipboardList :size="16" />
                            战报采集
                        </h3>
                    </div>
                    <div class="capture-tip">
                        <div class="tip-text">
                            <span class="tip-label">实时采集</span>
                            <span class="tip-desc">游戏中打开同盟战报页面自动抓取</span>
                        </div>
                        <n-space>
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
                        <div class="scroll-config">
                            <div class="config-item">
                                <span class="config-label">滑动次数</span>
                                <n-input-number v-model:value="scrollCount" :min="1" :max="50000" size="small" style="width: 100px" :disabled="autoScrollStatus.running" />
                            </div>
                            <div class="config-item">
                                <span class="config-label">间隔(ms)</span>
                                <n-input-number v-model:value="scrollDelay" :min="50" :max="5000" size="small" style="width: 80px" :disabled="autoScrollStatus.running" />
                            </div>
                            <div class="config-item">
                                <span class="config-label">时长(ms)</span>
                                <n-input-number v-model:value="scrollDuration" :min="50" :max="1000" size="small" style="width: 80px" :disabled="autoScrollStatus.running" />
                            </div>
                        </div>
                        <div class="scroll-screen">
                            <span class="screen-info">屏幕: {{ autoScrollStatus.screen_width }}x{{ autoScrollStatus.screen_height }}</span>
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
    background: #fff;
    border-radius: 10px;
    border: 1px solid #f0f0f0;

    .stat-icon {
        width: 40px; height: 40px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .stat-info { display: flex; flex-direction: column; }
    .stat-value { font-size: 20px; font-weight: 600; color: #333; }
    .stat-label { font-size: 12px; color: #999; }
}

.main-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.left-col, .right-col {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.card {
    background: #fff;
    border-radius: 10px;
    border: 1px solid #f0f0f0;
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
        color: #333;
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
    background: #fafafa;
    border-radius: 8px;

    .wu-rank {
        width: 22px; height: 22px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        background: #e8e8e8;
        font-size: 12px;
        font-weight: 600;
        color: #666;
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
        background: #fafafa;
        border-radius: 8px;

        .trend-label { font-size: 12px; color: #999; display: block; margin-bottom: 4px; }
        .trend-value { font-size: 20px; font-weight: 600; color: #333; }
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
    background: #fafafa;
    border-radius: 8px;
    text-decoration: none;
    color: inherit;
    transition: all 0.2s;

    &:hover { background: #f0f5ff; }

    .quick-icon {
        width: 32px; height: 32px;
        border-radius: 6px;
        background: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #666;
    }

    .quick-info {
        display: flex;
        flex-direction: column;
        .quick-label { font-size: 13px; font-weight: 500; }
        .quick-desc { font-size: 11px; color: #999; }
    }
}

.capture-tip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px;
    background: #fafaff;
    border-radius: 8px;

    .tip-text { display: flex; flex-direction: column; }
    .tip-label { font-size: 13px; font-weight: 500; }
    .tip-desc { font-size: 11px; color: #999; }
}

.auto-scroll-panel {
    padding: 12px;
    background: #fafaff;
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
    }

    .scroll-screen {
        margin-bottom: 12px;
        .screen-info { font-size: 11px; color: #999; }
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