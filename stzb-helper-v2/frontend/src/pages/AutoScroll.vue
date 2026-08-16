<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { NCard, NButton, NInput, NInputNumber, NSpace, NTag, NProgress, NAlert, NEmpty, NSwitch, useMessage, NSelect, NModal, NFormItem } from 'naive-ui'
import { LoadConfig, SaveConfig, CheckAdbConnection, GetAutoScrollStatus, StartAutoScroll, StopAutoScroll, SaveAdbProfiles, SetActiveAdbProfile, ScanAdbDevices, DiscoverAdbPaths } from '../../wailsjs/go/main/App'
import { RefreshCw, Wifi, WifiOff, Play, Square, Save, Monitor, Plus, Pencil, Trash2, Smartphone } from 'lucide-vue-next'

const nmessage = useMessage()

const config = ref<any>({
    adb_path: '',
    adb_serial: '',
    adb_profiles: [],
    active_adb_profile_id: '',
    scroll_count: 8000,
    scroll_delay: 100,
    scroll_duration: 100,
    stop_on_duplicate: false,
    default_dis_max_level: 19,
    default_atk_min_level: 25,
})

const loading = ref(false)
const checking = ref(false)
const adbConnected = ref(false)
const screenSize = ref('未知')
const status = ref({
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
const logs = ref<string[]>([])
const starting = ref(false)
let statusTimer: any = null

const showProfileModal = ref(false)
const savingProfiles = ref(false)
const profileForm = ref<any>({ id: '', name: '', adb_path: '', adb_serial: '' })
const editingProfile = ref(false)

const showScannedModal = ref(false)
const scannedDevices = ref<any[]>([])
const scanningDevices = ref(false)
const discoveredAdbPaths = ref<any[]>([])
const discoveringAdbPaths = ref(false)

const activeProfileOptions = computed(() => (config.value.adb_profiles || []).map((profile: any) => ({
    label: `${profile.name} (${profile.adb_serial})`,
    value: profile.id,
})))

const currentProfile = computed(() => {
    return (config.value.adb_profiles || []).find((profile: any) => profile.id === config.value.active_adb_profile_id) || null
})
const discoveredAdbOptions = computed(() => discoveredAdbPaths.value.map((item: any) => ({
    label: `${item.source || '本机ADB'} - ${item.path}`,
    value: item.path,
})))
const activeDatabaseName = computed(() => {
    const path = status.value.active_database_path || ''
    if (!path) return ''
    const parts = path.split(/[\\/]/)
    return parts[parts.length - 1] || path
})
const duplicateStrategyLabel = computed(() => status.value.stop_on_duplicate ? '发现重复后停止' : '发现重复后继续')

const progressPercent = computed(() => {
    if (status.value.total === 0) return 0
    return Math.round((status.value.current / status.value.total) * 100)
})

const addLog = (msg: string) => {
    const time = new Date().toLocaleTimeString('zh-CN')
    logs.value.push(`[${time}] ${msg}`)
    if (logs.value.length > 200) {
        logs.value = logs.value.slice(-200)
    }
}

const normalizeProfiles = (respData: any) => ({
    adb_path: typeof respData?.adb_path === 'string' ? respData.adb_path : '',
    adb_serial: typeof respData?.adb_serial === 'string' ? respData.adb_serial : '',
    adb_profiles: Array.isArray(respData?.adb_profiles) ? respData.adb_profiles : [],
    active_adb_profile_id: typeof respData?.active_adb_profile_id === 'string' ? respData.active_adb_profile_id : '',
    scroll_count: typeof respData?.scroll_count === 'number' ? respData.scroll_count : 8000,
    scroll_delay: typeof respData?.scroll_delay === 'number' ? respData.scroll_delay : 100,
    scroll_duration: typeof respData?.scroll_duration === 'number' ? respData.scroll_duration : 100,
    stop_on_duplicate: typeof respData?.stop_on_duplicate === 'boolean' ? respData.stop_on_duplicate : false,
    default_dis_max_level: typeof respData?.default_dis_max_level === 'number' ? respData.default_dis_max_level : 19,
    default_atk_min_level: typeof respData?.default_atk_min_level === 'number' ? respData.default_atk_min_level : 25,
})

const loadConfig = () => {
    loading.value = true
    return LoadConfig().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200 && resp.data) {
            config.value = normalizeProfiles(resp.data)
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

const saveScrollConfig = () => {
    SaveConfig(JSON.stringify(config.value)).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            nmessage.success('翻页配置已保存')
            addLog('翻页配置已保存')
        } else {
            nmessage.error(resp.msg)
            addLog('保存翻页配置失败: ' + resp.msg)
        }
    }).catch(e => {
        nmessage.error('保存失败: ' + e)
        addLog('保存翻页配置失败: ' + e)
    })
}

const saveProfiles = () => {
    savingProfiles.value = true
    SaveAdbProfiles(JSON.stringify({
        adb_profiles: config.value.adb_profiles,
        active_adb_profile_id: config.value.active_adb_profile_id,
    })).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            config.value = normalizeProfiles({ ...config.value, ...resp.data })
            nmessage.success(resp.msg)
            addLog(resp.msg)
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('保存模拟器实例失败: ' + e)
    }).finally(() => {
        savingProfiles.value = false
    })
}

const checkConnection = () => {
    checking.value = true
    addLog('检查ADB连接...')
    CheckAdbConnection('').then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200 && resp.data.connected) {
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

const fetchStatus = (syncPolling = false) => {
    GetAutoScrollStatus().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200 && resp.data) {
            status.value = resp.data
            if (syncPolling) {
                if (resp.data.running) {
                    startPolling()
                } else {
                    stopPolling()
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
        adb_path: '',
        adb_serial: '',
        count: Number(config.value.scroll_count) || 5000,
        delay: Number(config.value.scroll_delay) || 100,
        duration: Number(config.value.scroll_duration) || 100,
        stop_on_duplicate: !!config.value.stop_on_duplicate
    })).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
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
        const resp = JSON.parse(v)
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

const changeActiveProfile = (profileId: string) => {
    if (status.value.running) {
        nmessage.warning('自动翻页运行中，不能切换模拟器实例')
        return
    }
    SetActiveAdbProfile(profileId).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            config.value.active_adb_profile_id = profileId
            const profile = currentProfile.value
            if (profile) {
                config.value.adb_path = profile.adb_path
                config.value.adb_serial = profile.adb_serial
            }
            nmessage.success(resp.msg)
            addLog(resp.msg)
            checkConnection()
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('切换模拟器实例失败: ' + e)
    })
}

const openAddProfile = () => {
    editingProfile.value = false
    profileForm.value = { id: '', name: '', adb_path: currentProfile.value?.adb_path || config.value.adb_path || '', adb_serial: '' }
    discoveredAdbPaths.value = []
    showProfileModal.value = true
}

const openEditProfile = (profile: any) => {
    editingProfile.value = true
    profileForm.value = { ...profile }
    discoveredAdbPaths.value = []
    showProfileModal.value = true
}

const discoverAdbPaths = () => {
    discoveringAdbPaths.value = true
    DiscoverAdbPaths().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            discoveredAdbPaths.value = Array.isArray(resp.data) ? resp.data : []
            if (discoveredAdbPaths.value.length === 0) {
                nmessage.warning('没有检索到本机 ADB，可以继续使用内置 ADB 或手动填写路径')
                return
            }
            if (!profileForm.value.adb_path) {
                profileForm.value.adb_path = discoveredAdbPaths.value[0].path
            }
            nmessage.success(`已检索到 ${discoveredAdbPaths.value.length} 个 ADB 路径`)
        } else {
            nmessage.error(resp.msg || '检索ADB失败')
        }
    }).catch(e => {
        nmessage.error('检索ADB失败: ' + e)
    }).finally(() => {
        discoveringAdbPaths.value = false
    })
}

const persistProfileForm = () => {
    const payload = {
        ...profileForm.value,
        id: profileForm.value.id || `profile-${Date.now()}`,
        name: (profileForm.value.name || '').trim(),
        adb_path: (profileForm.value.adb_path || '').trim(),
        adb_serial: (profileForm.value.adb_serial || '').trim(),
    }
    if (!payload.name || !payload.adb_path || !payload.adb_serial) {
        nmessage.warning('请填写完整的实例名称、ADB路径和ADB Serial')
        return
    }

    const profiles = [...(config.value.adb_profiles || [])]
    const idx = profiles.findIndex((item: any) => item.id === payload.id)
    if (idx >= 0) {
        profiles[idx] = payload
    } else {
        profiles.push(payload)
    }
    config.value.adb_profiles = profiles
    if (!config.value.active_adb_profile_id) {
        config.value.active_adb_profile_id = payload.id
    }
    showProfileModal.value = false
    saveProfiles()
}

const removeProfile = (profile: any) => {
    if (status.value.running) {
        nmessage.warning('自动翻页运行中，不能删除模拟器实例')
        return
    }
    if ((config.value.adb_profiles || []).length <= 1) {
        nmessage.warning('至少保留一个模拟器实例')
        return
    }
    config.value.adb_profiles = (config.value.adb_profiles || []).filter((item: any) => item.id !== profile.id)
    if (config.value.active_adb_profile_id === profile.id) {
        config.value.active_adb_profile_id = config.value.adb_profiles[0]?.id || ''
    }
    saveProfiles()
}

const scanDevices = () => {
    scanningDevices.value = true
    ScanAdbDevices().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            scannedDevices.value = Array.isArray(resp.data) ? resp.data : []
            showScannedModal.value = true
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('扫描设备失败: ' + e)
    }).finally(() => {
        scanningDevices.value = false
    })
}

const addScannedDevice = (device: any) => {
    const existed = (config.value.adb_profiles || []).find((profile: any) => profile.adb_serial === device.serial)
    if (existed) {
        nmessage.warning('该设备已经在实例列表中')
        return
    }
    config.value.adb_profiles = [...(config.value.adb_profiles || []), {
        id: `profile-${Date.now()}`,
        name: device.name || `MuMu ${device.serial}`,
        adb_path: currentProfile.value?.adb_path || config.value.adb_path,
        adb_serial: device.serial,
    }]
    if (!config.value.active_adb_profile_id) {
        config.value.active_adb_profile_id = config.value.adb_profiles[config.value.adb_profiles.length - 1].id
    }
    saveProfiles()
}

onMounted(async () => {
    await loadConfig()
    checkConnection()
    fetchStatus(true)
})

onUnmounted(() => {
    stopPolling()
})
</script>

<template>
    <n-modal v-model:show="showProfileModal" preset="card" :title="editingProfile ? '编辑模拟器实例' : '新增模拟器实例'" size="small"
        style="width: min(460px, calc(100vw - 48px))" :mask-closable="false" to="body">
        <div class="modal-form">
            <n-form-item label="实例名称">
                <n-input v-model:value="profileForm.name" placeholder="例如：MuMu 16384" />
            </n-form-item>
            <n-form-item label="ADB 路径">
                <n-input v-model:value="profileForm.adb_path" placeholder="如: C:\adb\adb.exe" />
            </n-form-item>
            <n-space align="center" style="margin: -8px 0 12px;">
                <n-button size="small" :loading="discoveringAdbPaths" @click="discoverAdbPaths">检索本机ADB</n-button>
                <span class="modal-hint">优先使用安装包内置 ADB，也可选择本机已有 ADB。</span>
            </n-space>
            <n-form-item v-if="discoveredAdbOptions.length" label="检索结果">
                <n-select
                    v-model:value="profileForm.adb_path"
                    :options="discoveredAdbOptions"
                    filterable
                    placeholder="选择一个 ADB 路径"
                />
            </n-form-item>
            <n-form-item label="ADB Serial">
                <n-input v-model:value="profileForm.adb_serial" placeholder="如: 127.0.0.1:16384" />
            </n-form-item>
        </div>
        <template #footer>
            <n-space justify="end">
                <n-button type="primary" :loading="savingProfiles" @click="persistProfileForm">保存实例</n-button>
                <n-button @click="showProfileModal = false">取消</n-button>
            </n-space>
        </template>
    </n-modal>

    <n-modal v-model:show="showScannedModal" preset="card" title="扫描到的设备" size="huge"
        style="width: min(680px, calc(100vw - 48px))" :mask-closable="true" to="body">
        <div class="scanned-list" v-if="scannedDevices.length">
            <div class="scanned-item" v-for="device in scannedDevices" :key="device.serial">
                <div class="scanned-info">
                    <div class="scanned-name">{{ device.name }}</div>
                    <div class="scanned-meta">{{ device.serial }} / {{ device.status }}</div>
                </div>
                <n-button size="small" type="primary" @click="addScannedDevice(device)">加入实例列表</n-button>
            </div>
        </div>
        <n-empty v-else description="未扫描到设备" />
    </n-modal>

    <div class="autoscroll-page">
        <div class="page-header">
            <h1 class="page-title">
                <RefreshCw :size="24" />
                自动翻页助手
            </h1>
            <p class="page-desc">自动滑动游戏战报页面，配合抓包工具采集数据</p>
        </div>

        <div class="page-content">
            <div class="config-grid">
                <n-card title="模拟器实例" class="config-card">
                    <div class="form-group">
                        <label class="form-label">当前实例</label>
                        <n-select
                            :value="config.active_adb_profile_id"
                            :options="activeProfileOptions"
                            placeholder="请选择模拟器实例"
                            :disabled="status.running"
                            @update:value="changeActiveProfile"
                        />
                    </div>
                    <div class="profile-actions">
                        <n-button @click="openAddProfile" :disabled="status.running">
                            <template #icon><Plus :size="14" /></template>
                            新增实例
                        </n-button>
                        <n-button @click="scanDevices" :loading="scanningDevices" :disabled="status.running">
                            <template #icon><Smartphone :size="14" /></template>
                            扫描设备
                        </n-button>
                    </div>
                    <div class="profile-list" v-if="config.adb_profiles?.length">
                        <div class="profile-item" v-for="profile in config.adb_profiles" :key="profile.id">
                            <div class="profile-info">
                                <div class="profile-name-row">
                                    <span class="profile-name">{{ profile.name }}</span>
                                    <n-tag v-if="profile.id === config.active_adb_profile_id" type="success" size="small">当前</n-tag>
                                </div>
                                <div class="profile-meta">{{ profile.adb_serial }}</div>
                                <div class="profile-meta profile-path">{{ profile.adb_path }}</div>
                            </div>
                            <n-space>
                                <n-button size="tiny" quaternary @click="openEditProfile(profile)" :disabled="status.running">
                                    <template #icon><Pencil :size="12" /></template>
                                </n-button>
                                <n-button size="tiny" quaternary type="error" @click="removeProfile(profile)" :disabled="status.running">
                                    <template #icon><Trash2 :size="12" /></template>
                                </n-button>
                            </n-space>
                        </div>
                    </div>
                </n-card>

                <n-card title="连接与状态" class="config-card">
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
                        <n-button @click="checkConnection" :loading="checking" :disabled="status.running">检查连接</n-button>
                        <n-button type="primary" @click="saveScrollConfig" :disabled="status.running">
                            <template #icon><Save :size="14" /></template>
                            保存翻页配置
                        </n-button>
                    </div>
                </n-card>

                <n-card title="翻页配置" class="config-card">
                    <div class="config-row">
                        <div class="form-group">
                            <label class="form-label">滑动次数</label>
                            <n-input-number v-model:value="config.scroll_count" :min="1" :max="50000" :disabled="status.running" style="width: 150px" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">间隔(ms)</label>
                            <n-input-number v-model:value="config.scroll_delay" :min="50" :max="5000" :disabled="status.running" style="width: 140px" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">时长(ms)</label>
                            <n-input-number v-model:value="config.scroll_duration" :min="50" :max="1000" :disabled="status.running" style="width: 140px" />
                        </div>
                    </div>
                </n-card>

                <n-card title="状态与控制" class="config-card">
                    <div class="status-section">
                        <div class="status-row">
                            <n-tag v-if="status.running" type="success" size="large">运行中</n-tag>
                            <n-tag v-else type="default" size="large">已停止</n-tag>
                            <span class="status-text" v-if="status.running">{{ status.current }} / {{ status.total }} 次</span>
                        </div>
                        <div class="status-summary">
                            <div class="summary-row">
                                <span class="summary-label">当前写入数据库</span>
                                <span class="summary-value">{{ activeDatabaseName || '未连接数据库' }}</span>
                            </div>
                            <div v-if="status.active_database_path" class="summary-path">{{ status.active_database_path }}</div>
                            <div class="summary-row">
                                <span class="summary-label">重复策略</span>
                                <span class="summary-value">{{ duplicateStrategyLabel }}</span>
                            </div>
                            <div class="summary-grid">
                                <div class="summary-card">
                                    <span class="summary-card-label">新增战报</span>
                                    <strong>{{ status.inserted_count }}</strong>
                                </div>
                                <div class="summary-card">
                                    <span class="summary-card-label">重复战报</span>
                                    <strong>{{ status.duplicate_count }}</strong>
                                </div>
                                <div class="summary-card">
                                    <span class="summary-card-label">最后 battle_id</span>
                                    <strong>{{ status.last_battle_id || '-' }}</strong>
                                </div>
                            </div>
                        </div>
                        <div v-if="!status.running && status.stop_reason" class="stop-reason">{{ status.stop_reason }}</div>
                        <n-progress v-if="status.running" type="line" :percentage="progressPercent" :indicator-placement="'inside'" />
                    </div>
                    <div class="control-buttons">
                        <div class="duplicate-toggle">
                            <span>重复战报自动停</span>
                            <n-switch v-model:value="config.stop_on_duplicate" :disabled="status.running" />
                        </div>
                        <n-button v-if="!status.running" type="primary" size="large" @click="startScroll" :loading="starting" :disabled="!adbConnected">
                            <template #icon><Play :size="16" /></template>
                            开始翻页
                        </n-button>
                        <n-button v-else type="error" size="large" @click="stopScroll">
                            <template #icon><Square :size="16" /></template>
                            停止
                        </n-button>
                    </div>
                    <n-alert v-if="!adbConnected" type="warning" :show-icon="true">请先检查ADB连接，确保模拟器已开启</n-alert>
                </n-card>
            </div>

            <n-card title="运行日志" class="log-card">
                <template #header-extra>
                    <n-button size="small" @click="clearLogs">清空</n-button>
                </template>
                <div class="log-container">
                    <div v-if="logs.length === 0" class="log-empty">
                        <n-empty description="暂无日志" />
                    </div>
                    <div v-else class="log-list">
                        <div v-for="(log, i) in logs" :key="i" class="log-item">{{ log }}</div>
                    </div>
                </div>
            </n-card>
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

.config-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
}

.config-card {
    :deep(.n-card__content) {
        padding: 16px;
    }
}

.log-card {
    :deep(.n-card__content) {
        padding: 0;
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

.profile-actions {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
}

.profile-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.profile-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 12px;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-bg);
}

.profile-info {
    flex: 1;
}

.profile-name-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.profile-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text);
}

.profile-meta {
    font-size: 12px;
    color: var(--color-text-secondary);
}

.profile-path {
    word-break: break-all;
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

.status-summary {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
    padding: 12px;
    border: 1px solid var(--color-border-light);
    border-radius: 10px;
    background: var(--color-surface-hover);
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

.summary-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px;
    border: 1px solid var(--color-border-light);
    border-radius: 8px;
    background: var(--color-surface);
}

.summary-card-label {
    font-size: 12px;
    color: var(--color-text-secondary);
}

.stop-reason {
    margin-bottom: 12px;
    padding: 8px 10px;
    border: 1px solid var(--color-border-light);
    border-radius: 8px;
    background: var(--color-surface-hover);
    color: var(--color-text);
    font-size: 13px;
    line-height: 1.5;
}

.control-buttons {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-bottom: 16px;
}

.duplicate-toggle {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 34px;
    padding: 0 10px;
    border: 1px solid var(--color-border-light);
    border-radius: 8px;
    background: var(--color-surface-hover);
    color: var(--color-text);
    font-size: 13px;
    white-space: nowrap;
}

.log-card {
    height: 400px;
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
    background: var(--log-bg);
    border: 1px solid var(--log-border);
    border-radius: 8px;
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
        background: transparent;
        .log-item {
            color: var(--log-text);
            word-break: break-all;
        }
    }
}

.modal-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.scanned-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.scanned-item {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: center;
    padding: 12px;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-bg);
}

.scanned-name {
    font-size: 14px;
    font-weight: 600;
}

.scanned-meta {
    font-size: 12px;
    color: var(--color-text-secondary);
}

@media (max-width: 768px) {
    .config-grid {
        grid-template-columns: 1fr;
    }

    .config-row {
        flex-direction: column;
    }

    .profile-actions,
    .form-actions,
    .control-buttons {
        flex-wrap: wrap;
        justify-content: flex-start;
    }
}
</style>
