<script setup lang="ts">
import { ref, onMounted, computed, watch, onUnmounted, h } from 'vue'
import {
    NCard, NButton, NSpace, NTag, NEmpty,
    NInput, NFormItem, NSelect, NDatePicker, NPopconfirm, NModal, NInputNumber,
    NDataTable, NStatistic, NAlert,
    useMessage
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import {
    GetTeamGroup, CreateTask, GetTaskList, DeleteTask,
    EnableGetReport, DisableGetReport, GetReportNumByTaskId, StatisticsReport, GetCaptureModeStatus,
    GetTask, DeleteTaskReport, UpdateTaskAttendanceRule, UpdateTask, GetAttendanceSummary,
    LoadConfig, SaveConfig
} from '../../wailsjs/go/main/App'
import { formatTimestampMs, splitwid } from '@/utils/format'
import { Plus, RefreshCw, Eye, Play, Trash2, Eraser, Pencil, LayoutGrid, Search } from 'lucide-vue-next'

const nmessage = useMessage()

const grouplist = ref<any[]>([])
const tasks = ref<any[]>([])
const loading = ref(false)
const taskNum = ref(0)
const searchKeyword = ref('')
const captureMode = ref({ mode: 'none', running: false, report_pos: 0, message: '当前未开启战报采集' })
const appConfig = ref<any>({
    adb_path: '',
    adb_serial: '',
    adb_profiles: [],
    active_adb_profile_id: '',
    scroll_count: 4000,
    scroll_delay: 100,
    scroll_duration: 100,
    stop_on_duplicate: false,
    database_path: '',
    default_dis_max_level: 19,
    default_atk_min_level: 25,
})
const attendanceDefaults = ref({ disMaxLevel: 19, atkMinLevel: 25 })
const savingDefaultRule = ref(false)

const defaultTaskForm = () => ({
    id: 0,
    name: '',
    time: new Date().getTime(),
    pos: ['', ''] as [string, string],
    target: [] as string[],
    disMaxLevel: attendanceDefaults.value.disMaxLevel as number | null,
    atkMinLevel: attendanceDefaults.value.atkMinLevel as number | null,
})

const addtaskshow = ref(false)
const editTaskShow = ref(false)
const createing = ref(false)
const updatingTask = ref(false)
const editWarning = ref('')
const taskForm = ref(defaultTaskForm())

const currentRule = ref({ dis_max_level: 0, atk_min_level: 0 })
const showRuleModal = ref(false)
const ruleTaskId = ref(0)
const ruleTaskName = ref('')
const ruleDisMaxLevel = ref<number | null>(null)
const ruleAtkMinLevel = ref<number | null>(null)
const savingRule = ref(false)
const pendingStatisticsTaskId = ref(0)

const showModal = ref(false)
const getReporting = ref(false)
const reportNum = ref(0)
const getReportNumTimer = ref<any>(null)
const inStatistics = ref(false)
const curtaskid = ref(0)
const curtaskpos = ref(0)

const showModal2 = ref(false)
const taskDetail = ref<any>({})

const showSummaryModal = ref(false)
const loadingSummary = ref(false)
const attendanceSummary = ref<any>({ tasks: [], members: [] })

const hasAttendanceRule = (task: any) => Number(task?.dis_max_level) > 0 && Number(task?.atk_min_level) > 0
const formatAttendanceRule = (task: any) => hasAttendanceRule(task)
    ? `拆迁 <= ${task.dis_max_level} 级，主力 >= ${task.atk_min_level} 级`
    : '未配置考勤等级规则'

const validateRule = (disMaxLevel: number | null, atkMinLevel: number | null) => {
    if (!disMaxLevel || !atkMinLevel) return '请填写主力/拆迁等级规则'
    if (disMaxLevel >= atkMinLevel) return '拆迁最高等级必须小于主力最低等级'
    return ''
}

const ensureArray = (value: any) => Array.isArray(value) ? value : []
const allGroupValues = computed(() => grouplist.value.map((group: any) => group.value))
const normalizeAppConfig = (value: any) => ({
    adb_path: typeof value?.adb_path === 'string' ? value.adb_path : '',
    adb_serial: typeof value?.adb_serial === 'string' ? value.adb_serial : '',
    adb_profiles: ensureArray(value?.adb_profiles),
    active_adb_profile_id: typeof value?.active_adb_profile_id === 'string' ? value.active_adb_profile_id : '',
    scroll_count: typeof value?.scroll_count === 'number' ? value.scroll_count : 4000,
    scroll_delay: typeof value?.scroll_delay === 'number' ? value.scroll_delay : 100,
    scroll_duration: typeof value?.scroll_duration === 'number' ? value.scroll_duration : 100,
    stop_on_duplicate: typeof value?.stop_on_duplicate === 'boolean' ? value.stop_on_duplicate : false,
    database_path: typeof value?.database_path === 'string' ? value.database_path : '',
    default_dis_max_level: typeof value?.default_dis_max_level === 'number' ? value.default_dis_max_level : 19,
    default_atk_min_level: typeof value?.default_atk_min_level === 'number' ? value.default_atk_min_level : 25,
})

const filteredTasks = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (!keyword) return tasks.value
    return tasks.value.filter((task: any) => String(task.name || '').toLowerCase().includes(keyword))
})

const taskCountText = computed(() => {
    if (!searchKeyword.value.trim()) return `任务数量：${taskNum.value}`
    return `匹配 ${filteredTasks.value.length} / 总计 ${taskNum.value}`
})

const isTaskBeingCaptured = (task: any) => captureMode.value.mode === 'attendance_report' && captureMode.value.report_pos === task.pos

const resetTaskForm = () => {
    taskForm.value = defaultTaskForm()
    editWarning.value = ''
}

const fillTaskForm = (task?: any) => {
    if (!task) {
        resetTaskForm()
        return
    }
    taskForm.value = {
        id: task.id || 0,
        name: task.name || '',
        time: task.time || new Date().getTime(),
        pos: (splitwid(task.pos || 0).split(',') as [string, string]),
        target: ensureArray(task.target),
        disMaxLevel: task.dis_max_level || null,
        atkMinLevel: task.atk_min_level || null,
    }
    editWarning.value = Number(task.complete_user_num) > 0 || task.status === 1
        ? '该任务已有统计结果或旧战报口径。若修改坐标或目标分组，系统不会自动清理旧战报，建议先清理旧战报再重新采集/统计。'
        : ''
}

const loadGroups = () => {
    return GetTeamGroup().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            grouplist.value = ensureArray(resp.data).map((e: string) => ({ label: e, value: e }))
        }
    })
}

const loadTaskConfig = () => {
    return LoadConfig().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200 && resp.data) {
            appConfig.value = normalizeAppConfig(resp.data)
            attendanceDefaults.value = {
                disMaxLevel: appConfig.value.default_dis_max_level,
                atkMinLevel: appConfig.value.default_atk_min_level,
            }
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('读取全局默认考勤规则失败:' + e)
    })
}

const saveDefaultAttendanceRule = () => {
    const ruleError = validateRule(attendanceDefaults.value.disMaxLevel, attendanceDefaults.value.atkMinLevel)
    if (ruleError) {
        nmessage.warning(ruleError)
        return
    }
    savingDefaultRule.value = true
    const nextConfig = normalizeAppConfig({
        ...appConfig.value,
        default_dis_max_level: attendanceDefaults.value.disMaxLevel,
        default_atk_min_level: attendanceDefaults.value.atkMinLevel,
    })
    SaveConfig(JSON.stringify(nextConfig)).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            appConfig.value = nextConfig
            nmessage.success('全局默认考勤等级规则已保存')
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('保存全局默认考勤规则失败:' + e)
    }).finally(() => {
        savingDefaultRule.value = false
    })
}

const selectAllGroupsForTask = () => {
    if (!allGroupValues.value.length) {
        nmessage.warning('当前还没有可选分组')
        return
    }
    taskForm.value.target = [...allGroupValues.value]
}

function getTaskList() {
    loading.value = true
    tasks.value = []
    taskNum.value = 0
    return GetTaskList().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            tasks.value = ensureArray(resp.data)
            taskNum.value = tasks.value.length
        } else {
            nmessage.error(resp.msg)
        }
    }).finally(() => {
        loading.value = false
    })
}

const refreshCaptureMode = () => {
    GetCaptureModeStatus().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            captureMode.value = resp.data
        }
    }).catch(() => {})
}

const openCreateModal = () => {
    resetTaskForm()
    addtaskshow.value = true
}

const createTask = () => {
    const ruleError = validateRule(taskForm.value.disMaxLevel, taskForm.value.atkMinLevel)
    if (ruleError) {
        nmessage.warning(ruleError)
        return
    }
    createing.value = true
    CreateTask(
        taskForm.value.name,
        taskForm.value.time,
        taskForm.value.target,
        taskForm.value.pos,
        taskForm.value.disMaxLevel!,
        taskForm.value.atkMinLevel!,
    ).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            nmessage.success(resp.msg)
            addtaskshow.value = false
            resetTaskForm()
            getTaskList()
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error(String(e))
    }).finally(() => {
        createing.value = false
    })
}

const openEditTask = (task: any) => {
    if (isTaskBeingCaptured(task)) {
        nmessage.warning('该任务当前正在考勤采集中，请先停止当前考勤模式再编辑')
        return
    }
    fillTaskForm(task)
    editTaskShow.value = true
}

const saveEditedTask = () => {
    const ruleError = validateRule(taskForm.value.disMaxLevel, taskForm.value.atkMinLevel)
    if (ruleError) {
        nmessage.warning(ruleError)
        return
    }
    updatingTask.value = true
    UpdateTask(
        taskForm.value.id,
        taskForm.value.name,
        taskForm.value.time,
        taskForm.value.target,
        taskForm.value.pos,
        taskForm.value.disMaxLevel!,
        taskForm.value.atkMinLevel!,
    ).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            nmessage.success(resp.msg)
            editTaskShow.value = false
            getTaskList()
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('保存任务失败:' + e)
    }).finally(() => {
        updatingTask.value = false
    })
}

const delTask = (id: number) => {
    DeleteTask(id).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            nmessage.success(resp.msg)
            getTaskList()
        } else {
            nmessage.error(resp.msg)
        }
    })
}

const delTaskReport = (id: number) => {
    DeleteTaskReport(id).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            nmessage.success(resp.msg)
            getTaskList()
        } else {
            nmessage.error(resp.msg)
        }
    })
}

const openRuleModal = (task: any, options?: { forStatistics?: boolean }) => {
    ruleTaskId.value = task.id
    ruleTaskName.value = task.name || `任务#${task.id}`
    ruleDisMaxLevel.value = task.dis_max_level || null
    ruleAtkMinLevel.value = task.atk_min_level || null
    pendingStatisticsTaskId.value = options?.forStatistics ? task.id : 0
    showRuleModal.value = true
}

const saveAttendanceRule = () => {
    const ruleError = validateRule(ruleDisMaxLevel.value, ruleAtkMinLevel.value)
    if (ruleError) {
        nmessage.warning(ruleError)
        return
    }
    savingRule.value = true
    UpdateTaskAttendanceRule(ruleTaskId.value, ruleDisMaxLevel.value!, ruleAtkMinLevel.value!).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            nmessage.success(resp.msg)
            currentRule.value = {
                dis_max_level: resp.data.dis_max_level || 0,
                atk_min_level: resp.data.atk_min_level || 0,
            }
            taskDetail.value = resp.data
            showRuleModal.value = false
            getTaskList()
            if (pendingStatisticsTaskId.value === resp.data.id) {
                pendingStatisticsTaskId.value = 0
                statisticsWithTask(resp.data)
            }
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('保存考勤等级规则失败:' + e)
    }).finally(() => {
        savingRule.value = false
    })
}

const stopReportPolling = () => {
    clearInterval(getReportNumTimer.value)
    getReportNumTimer.value = null
    getReporting.value = false
    inStatistics.value = false
}

const startReportPolling = (id: number) => {
    stopReportPolling()
    getReporting.value = true
    GetReportNumByTaskId(id).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            reportNum.value = resp.data.count
        }
    }).catch(() => {})
    getReportNumTimer.value = setInterval(() => {
        GetReportNumByTaskId(id).then(v => {
            const resp = JSON.parse(v)
            if (resp.code === 200) {
                reportNum.value = resp.data.count
            }
        })
        refreshCaptureMode()
    }, 1000)
}

const openReportModal = (id: number, pos: number) => {
    curtaskid.value = id
    curtaskpos.value = pos
    reportNum.value = 0
    showModal.value = true
    startReportPolling(id)
}

const enableGetReport = (id: number, pos: number) => {
    EnableGetReport(pos).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            captureMode.value = resp.data
            openReportModal(id, pos)
            nmessage.success(resp.msg)
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('开启考勤模式失败:' + e)
    })
}

const disableAttendanceMode = () => {
    stopReportPolling()
    DisableGetReport().finally(() => {
        refreshCaptureMode()
    })
}

const statisticsWithTask = (task: any) => {
    stopReportPolling()
    inStatistics.value = true
    currentRule.value = {
        dis_max_level: task.dis_max_level || 0,
        atk_min_level: task.atk_min_level || 0,
    }
    StatisticsReport(task.id).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            taskDetail.value = resp.data
            showModal2.value = true
            nmessage.success(resp.msg)
            curtaskid.value = 0
            getTaskList()
        } else {
            nmessage.error(resp.msg)
        }
        inStatistics.value = false
        showModal.value = false
        refreshCaptureMode()
    }).catch(e => {
        inStatistics.value = false
        nmessage.error('统计考勤数据失败:' + e)
        refreshCaptureMode()
    })
}

const statistics = () => {
    const task = tasks.value.find((item: any) => item.id === curtaskid.value)
    if (!task) {
        nmessage.error('任务不存在或已刷新，请重新打开考勤任务')
        return
    }
    if (!hasAttendanceRule(task)) {
        openRuleModal(task, { forStatistics: true })
        return
    }
    statisticsWithTask(task)
}

const getTaskDetail = (id: number) => {
    taskDetail.value = {}
    showModal2.value = true
    GetTask(id).then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            taskDetail.value = resp.data
            currentRule.value = {
                dis_max_level: resp.data.dis_max_level || 0,
                atk_min_level: resp.data.atk_min_level || 0,
            }
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('获取考勤数据失败:' + e)
    })
}

const exportExcel = async () => {
    const XLSX = await import('xlsx')
    // 明细表
    const data = [['名字', '分组', '主力', '拆迁', '主力次数', '拆迁次数', '未到']]
    Object.values(taskDetail.value.user_list || {}).forEach((v: any) => {
        const absent = v.atk_num === 0 && v.dis_num === 0 ? '未到' : ''
        data.push([v.name, v.group, v.atk_team_num, v.dis_team_num, v.atk_num, v.dis_num, absent])
    })
    const ws = XLSX.utils.aoa_to_sheet(data)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '考勤明细')
    // 团汇总表
    const summaryData = [
        ['团', '人数', '主力次数', '拆迁次数', '缺勤人数'],
        ...groupSummaryData.value.map((g: any) => [g.group, g.member_count, g.atk_num_total, g.dis_num_total, g.absent_count]),
    ]
    const wsSummary = XLSX.utils.aoa_to_sheet(summaryData)
    XLSX.utils.book_append_sheet(wb, wsSummary, '团汇总')
    XLSX.writeFile(wb, `${taskDetail.value.name}考勤表.xlsx`)
}

const loadAttendanceSummary = () => {
    loadingSummary.value = true
    GetAttendanceSummary().then(v => {
        const resp = JSON.parse(v)
        if (resp.code === 200) {
            attendanceSummary.value = resp.data || { tasks: [], members: [] }
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('获取考勤总览失败:' + e)
    }).finally(() => {
        loadingSummary.value = false
    })
}

const openSummaryModal = () => {
    showSummaryModal.value = true
    loadAttendanceSummary()
}

const formatSummaryCell = (cell: any) => {
    if (!cell?.in_roster) return '-'
    if (!cell.attended) return '未到'
    return `到 (主${cell.atk_num || 0}/拆${cell.dis_num || 0})`
}

const summaryColumns = computed<DataTableColumns<any>>(() => {
    const base = [
        { title: '姓名', key: 'name', width: 110, fixed: 'left' as const },
        { title: '分组', key: 'group', width: 90, fixed: 'left' as const },
        { title: '到场任务', key: 'task_attended_count', width: 90, fixed: 'left' as const },
        { title: '未到任务', key: 'task_absent_count', width: 90 },
        { title: '主力总次数', key: 'atk_num_total', width: 100 },
        { title: '拆迁总次数', key: 'dis_num_total', width: 100 },
    ]
    const taskColumns = ensureArray(attendanceSummary.value.tasks).map((task: any) => ({
        title: `${task.name}\n${formatTimestampMs(task.time)}`,
        key: `task_${task.id}`,
        width: 150,
        render: (row: any) => h('span', formatSummaryCell(row.task_map?.[task.id])),
    }))
    return [...base, ...taskColumns]
})

const exportSummaryExcel = async () => {
    const XLSX = await import('xlsx')
    const tasksForSummary = ensureArray(attendanceSummary.value.tasks)
    const members = ensureArray(attendanceSummary.value.members)
    const header = ['姓名', '分组', '到场任务', '未到任务', '主力总次数', '拆迁总次数', ...tasksForSummary.map((task: any) => task.name)]
    const rows = members.map((member: any) => [
        member.name,
        member.group,
        member.task_attended_count,
        member.task_absent_count,
        member.atk_num_total,
        member.dis_num_total,
        ...tasksForSummary.map((task: any) => formatSummaryCell(member.task_map?.[task.id])),
    ])
    const ws = XLSX.utils.aoa_to_sheet([header, ...rows])
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '考勤总览')
    XLSX.writeFile(wb, '攻城考勤总览.xlsx')
}

const detailColumns: any[] = [
    { title: '名称', key: 'name', sorter: 'default', defaultSortOrder: false },
    { title: '分组', key: 'group', sorter: 'default', defaultSortOrder: false },
    { title: '主力', key: 'atk_team_num', sorter: (a: any, b: any) => a.atk_team_num - b.atk_team_num, defaultSortOrder: false },
    { title: '拆迁', key: 'dis_team_num', sorter: (a: any, b: any) => a.dis_team_num - b.dis_team_num, defaultSortOrder: false },
    { title: '主力次数', key: 'atk_num', sorter: (a: any, b: any) => a.atk_num - b.atk_num, defaultSortOrder: 'descend' },
    { title: '拆迁次数', key: 'dis_num', sorter: (a: any, b: any) => a.dis_num - b.dis_num, defaultSortOrder: false },
    { title: '未到', key: 'absent', width: 80, render: (row: any) => h('span', row.atk_num === 0 && row.dis_num === 0 ? '未到' : ''), sorter: (a: any, b: any) => (a.atk_num === 0 && a.dis_num === 0 ? 1 : 0) - (b.atk_num === 0 && b.dis_num === 0 ? 1 : 0) },
]

const groupSummaryColumns: any[] = [
    { title: '团', key: 'group', width: 120, sorter: 'default' },
    { title: '人数', key: 'member_count', width: 80, sorter: (a: any, b: any) => a.member_count - b.member_count },
    { title: '主力次数', key: 'atk_num_total', width: 110, sorter: (a: any, b: any) => a.atk_num_total - b.atk_num_total, defaultSortOrder: 'descend' },
    { title: '拆迁次数', key: 'dis_num_total', width: 110, sorter: (a: any, b: any) => a.dis_num_total - b.dis_num_total },
    { title: '缺勤人数', key: 'absent_count', width: 110, sorter: (a: any, b: any) => a.absent_count - b.absent_count },
]

const detailData = computed(() => {
    if (!taskDetail.value.user_list) return []
    return Object.values(taskDetail.value.user_list)
})

// 按团（分组）汇总：主力次数、拆迁次数、缺勤人数
const groupSummaryData = computed(() => {
    const map: Record<string, any> = {}
    for (const u of detailData.value as any[]) {
        const g = u.group || '未分组'
        if (!map[g]) {
            map[g] = { group: g, member_count: 0, atk_num_total: 0, dis_num_total: 0, absent_count: 0 }
        }
        const item = map[g]
        item.member_count++
        item.atk_num_total += u.atk_num || 0
        item.dis_num_total += u.dis_num || 0
        if ((u.atk_num || 0) === 0 && (u.dis_num || 0) === 0) {
            item.absent_count++
        }
    }
    return Object.values(map).sort((a: any, b: any) => a.group.localeCompare(b.group, 'zh'))
})

watch(showModal, (val) => {
    if (!val) stopReportPolling()
})

watch(showRuleModal, (val) => {
    if (!val) {
        pendingStatisticsTaskId.value = 0
    }
})

watch([addtaskshow, editTaskShow], ([addVisible, editVisible]) => {
    if (!addVisible && !editVisible) {
        resetTaskForm()
    }
})

onMounted(() => {
    loadGroups()
    loadTaskConfig()
    getTaskList()
    refreshCaptureMode()
})

onUnmounted(() => {
    stopReportPolling()
})
</script>

<template>
    <n-modal v-model:show="addtaskshow" preset="card" title="新增任务" size="huge" :bordered="false"
        style="width: min(520px, calc(100vw - 48px))" :mask-closable="false" to="body">
        <div class="modal-form">
            <n-form-item label="任务名称">
                <n-input v-model:value="taskForm.name" placeholder="例如：内黄LV5 或者你也可以随意填写" />
            </n-form-item>
            <n-form-item label="任务坐标">
                <n-input pair separator="，" :placeholder="['X坐标', 'Y坐标']" v-model:value="taskForm.pos" clearable />
            </n-form-item>
            <n-form-item label="任务时间">
                <n-date-picker v-model:value="taskForm.time" type="datetime" style="width: 100%;" />
            </n-form-item>
            <n-form-item label="目标分组">
                <div class="group-select-toolbar">
                    <n-button size="tiny" quaternary @click="selectAllGroupsForTask">一键全选当前分组</n-button>
                    <span class="group-select-count">已选 {{ taskForm.target.length }} / {{ grouplist.length }}</span>
                </div>
                <n-select v-model:value="taskForm.target" multiple :options="grouplist" placeholder="请选择分组" />
            </n-form-item>
            <n-form-item label="拆迁最高等级">
                <n-input-number v-model:value="taskForm.disMaxLevel" :min="1" :max="49" style="width: 100%;" />
            </n-form-item>
            <n-form-item label="主力最低等级">
                <n-input-number v-model:value="taskForm.atkMinLevel" :min="1" :max="50" style="width: 100%;" />
            </n-form-item>
        </div>
        <template #footer>
            <n-space justify="end">
                <n-button strong secondary type="primary" :loading="createing" @click="createTask">添加</n-button>
                <n-button strong secondary type="error" @click="addtaskshow = false">关闭</n-button>
            </n-space>
        </template>
    </n-modal>

    <n-modal v-model:show="editTaskShow" preset="card" title="编辑任务" size="huge" :bordered="false"
        style="width: min(560px, calc(100vw - 48px))" :mask-closable="false" to="body">
        <div class="modal-form">
            <n-alert v-if="editWarning" type="warning" :show-icon="true">
                {{ editWarning }}
            </n-alert>
            <n-form-item label="任务名称">
                <n-input v-model:value="taskForm.name" placeholder="请输入任务名称" />
            </n-form-item>
            <n-form-item label="任务坐标">
                <n-input pair separator="，" :placeholder="['X坐标', 'Y坐标']" v-model:value="taskForm.pos" clearable />
            </n-form-item>
            <n-form-item label="任务时间">
                <n-date-picker v-model:value="taskForm.time" type="datetime" style="width: 100%;" />
            </n-form-item>
            <n-form-item label="目标分组">
                <div class="group-select-toolbar">
                    <n-button size="tiny" quaternary @click="selectAllGroupsForTask">一键全选当前分组</n-button>
                    <span class="group-select-count">已选 {{ taskForm.target.length }} / {{ grouplist.length }}</span>
                </div>
                <n-select v-model:value="taskForm.target" multiple :options="grouplist" placeholder="请选择分组" />
            </n-form-item>
            <n-form-item label="拆迁最高等级">
                <n-input-number v-model:value="taskForm.disMaxLevel" :min="1" :max="49" style="width: 100%;" />
            </n-form-item>
            <n-form-item label="主力最低等级">
                <n-input-number v-model:value="taskForm.atkMinLevel" :min="1" :max="50" style="width: 100%;" />
            </n-form-item>
        </div>
        <template #footer>
            <n-space justify="end">
                <n-button strong secondary type="primary" :loading="updatingTask" @click="saveEditedTask">保存</n-button>
                <n-button strong secondary @click="editTaskShow = false">取消</n-button>
            </n-space>
        </template>
    </n-modal>

    <n-modal v-model:show="showRuleModal" preset="card" title="配置考勤等级规则" size="small"
        style="width: min(420px, calc(100vw - 48px))" :bordered="false" :mask-closable="false" to="body">
        <div class="modal-form">
            <div class="rule-modal-tip">当前任务：{{ ruleTaskName }}</div>
            <n-form-item label="拆迁最高等级">
                <n-input-number v-model:value="ruleDisMaxLevel" :min="1" :max="49" style="width: 100%;" />
            </n-form-item>
            <n-form-item label="主力最低等级">
                <n-input-number v-model:value="ruleAtkMinLevel" :min="1" :max="50" style="width: 100%;" />
            </n-form-item>
        </div>
        <template #footer>
            <n-space justify="end">
                <n-button strong secondary type="primary" :loading="savingRule" @click="saveAttendanceRule">保存规则</n-button>
                <n-button strong secondary @click="showRuleModal = false">取消</n-button>
            </n-space>
        </template>
    </n-modal>

    <n-modal v-model:show="showModal" preset="card" title="攻城考勤" size="huge" :bordered="false"
        style="width: min(600px, calc(100vw - 48px))" :mask-closable="false" to="body">
        <div class="report-modal">
            <p class="report-tip">请前往游戏中，到攻城任务坐标位置查看同盟战报，并勾选守城军士（否则获取不了拆迁战报）。然后一直往下滑直到没有战报为止</p>
            <p class="report-tip report-tip-secondary" v-if="currentRule.dis_max_level && currentRule.atk_min_level">
                当前统计规则：拆迁等级小于等于 {{ currentRule.dis_max_level }} 级；主力等级 {{ currentRule.atk_min_level }} 级及以上都计入考勤。
            </p>
            <p class="report-tip report-tip-secondary" v-else>
                当前任务尚未配置主力/拆迁等级规则，开始统计前需要先补充。
            </p>
            <n-tag type="warning" :bordered="false" class="report-mode-tag">当前处于考勤守军模式，已暂停详细战报采集</n-tag>
            <div class="report-status-row">
                <n-tag :bordered="false" type="success" v-if="captureMode.mode === 'attendance_report'">考勤模式已开启</n-tag>
                <n-tag :bordered="false" type="default" v-else>当前未处于考勤模式</n-tag>
                <n-tag :bordered="false" type="info" v-if="curtaskpos">目标坐标 {{ splitwid(curtaskpos) }}</n-tag>
            </div>
            <div class="report-counter">
                <n-statistic label="已获取战报" :value="reportNum">
                    <template #suffix>
                        <span style="font-size: 14px; color: #64748b;">封</span>
                    </template>
                </n-statistic>
            </div>
        </div>
        <template #footer>
            <n-space>
                <n-button strong secondary type="info" :loading="true" v-if="getReporting">获取战报中</n-button>
                <n-button strong secondary type="warning" @click="disableAttendanceMode">停止考勤模式</n-button>
                <n-button strong secondary type="success" @click="statistics" :loading="inStatistics">
                    {{ inStatistics ? '统计考勤数据中' : '已获取完战报，开始统计考勤数据' }}
                </n-button>
                <n-button strong secondary @click="showModal = false">关闭窗口</n-button>
            </n-space>
        </template>
    </n-modal>

    <n-modal v-model:show="showModal2" preset="card" title="考勤详情" size="huge" :bordered="false"
        style="width: min(1024px, calc(100vw - 48px))" :mask-closable="false" to="body">
        <div class="detail-modal">
            <div class="detail-summary" v-if="taskDetail.id">
                <div class="detail-summary-item">
                    <span class="detail-summary-label">任务名称</span>
                    <span class="detail-summary-value">{{ taskDetail.name }}</span>
                </div>
                <div class="detail-summary-item">
                    <span class="detail-summary-label">任务坐标</span>
                    <span class="detail-summary-value">{{ splitwid(taskDetail.pos) }}</span>
                </div>
                <div class="detail-summary-item">
                    <span class="detail-summary-label">目标人数</span>
                    <span class="detail-summary-value">{{ taskDetail.target_user_num || 0 }}</span>
                </div>
                <div class="detail-summary-item">
                    <span class="detail-summary-label">实到人数</span>
                    <span class="detail-summary-value">{{ taskDetail.complete_user_num || 0 }}</span>
                </div>
                <div class="detail-summary-item">
                    <span class="detail-summary-label">考勤规则</span>
                    <span class="detail-summary-value">{{ formatAttendanceRule(taskDetail) }}</span>
                </div>
            </div>
            <n-button type="primary" style="margin-bottom: 16px;" @click="exportExcel">导出为表格</n-button>
            <div class="group-summary-section" v-if="groupSummaryData.length">
                <div class="group-summary-title">按团汇总</div>
                <n-data-table :columns="groupSummaryColumns" :data="groupSummaryData" :bordered="true" :single-line="false" size="small" :max-height="300" style="margin-bottom: 16px;" />
            </div>
            <n-data-table :columns="detailColumns" :data="detailData" :bordered="true" :single-line="false" :max-height="500" />
        </div>
    </n-modal>

    <n-modal v-model:show="showSummaryModal" preset="card" title="所有任务考勤总览" size="huge" :bordered="false"
        style="width: min(1200px, calc(100vw - 48px))" :mask-closable="false" to="body">
        <div class="summary-modal">
            <div class="summary-actions">
                <n-space>
                    <n-button @click="loadAttendanceSummary" :loading="loadingSummary">
                        <template #icon><RefreshCw :size="14" /></template>
                        刷新总览
                    </n-button>
                    <n-button type="primary" @click="exportSummaryExcel" :disabled="!attendanceSummary.members?.length">
                        导出总览
                    </n-button>
                </n-space>
            </div>
            <n-data-table
                :columns="summaryColumns"
                :data="attendanceSummary.members || []"
                :loading="loadingSummary"
                :bordered="true"
                :single-line="false"
                :scroll-x="Math.max(1200, 580 + (attendanceSummary.tasks?.length || 0) * 150)"
                :max-height="560"
            />
        </div>
    </n-modal>

    <div class="page-task">
        <n-card class="page-card" embedded>
            <div class="page-header">
                <div class="page-header-info">
                    <h2 class="page-title">攻城任务</h2>
                    <p class="page-desc">{{ taskCountText }}</p>
                </div>
                <n-space>
                    <n-button @click="getTaskList" :loading="loading">
                        <template #icon><RefreshCw :size="16" /></template>
                        刷新
                    </n-button>
                    <n-button @click="openSummaryModal">
                        <template #icon><LayoutGrid :size="16" /></template>
                        考勤总览
                    </n-button>
                    <n-button type="primary" @click="openCreateModal">
                        <template #icon><Plus :size="16" /></template>
                        新增任务
                    </n-button>
                </n-space>
            </div>

            <div class="toolbar-row">
                <n-input v-model:value="searchKeyword" clearable placeholder="按任务名称搜索" class="search-input">
                    <template #prefix>
                        <Search :size="16" />
                    </template>
                </n-input>
            </div>

            <div class="default-rule-card">
                <div class="default-rule-header">
                    <div>
                        <div class="default-rule-title">全局默认考勤等级规则</div>
                        <div class="default-rule-desc">只影响下一次新建任务时的默认值，不会改动已有任务的统计口径。</div>
                    </div>
                    <n-button type="primary" secondary :loading="savingDefaultRule" @click="saveDefaultAttendanceRule">
                        保存全局默认值
                    </n-button>
                </div>
                <div class="default-rule-grid">
                    <n-form-item label="拆迁最高等级">
                        <n-input-number v-model:value="attendanceDefaults.disMaxLevel" :min="1" :max="49" style="width: 100%;" />
                    </n-form-item>
                    <n-form-item label="主力最低等级">
                        <n-input-number v-model:value="attendanceDefaults.atkMinLevel" :min="1" :max="50" style="width: 100%;" />
                    </n-form-item>
                </div>
            </div>

            <div class="capture-status-card">
                <div>
                    <div class="capture-status-title">当前采集模式</div>
                    <div class="capture-status-text">{{ captureMode.message }}</div>
                </div>
                <n-tag :type="captureMode.mode === 'attendance_report' ? 'success' : captureMode.mode === 'battle_detail' ? 'warning' : 'default'" :bordered="false">
                    {{ captureMode.mode === 'attendance_report' ? '考勤守军' : captureMode.mode === 'battle_detail' ? '详细战报' : '未开启' }}
                </n-tag>
            </div>

            <div class="task-list" v-if="filteredTasks.length > 0">
                <div class="task-card" v-for="task in filteredTasks" :key="task.id">
                    <div class="task-header">
                        <div class="task-title-row">
                            <span class="task-name">{{ task.name }}</span>
                            <span class="task-coords">({{ splitwid(task.pos) }})</span>
                        </div>
                    </div>

                    <div class="task-stats">
                        <div class="task-stat-item">
                            <span class="task-stat-label">目标分组</span>
                            <div class="task-stat-tags">
                                <n-tag :bordered="false" type="info" size="small" v-for="g in task.target" :key="g">{{ g }}</n-tag>
                            </div>
                        </div>
                        <div class="task-stat-item">
                            <span class="task-stat-label">目标人数</span>
                            <span class="task-stat-value">{{ task.target_user_num }}</span>
                        </div>
                        <div class="task-stat-item">
                            <span class="task-stat-label">实到人数</span>
                            <span class="task-stat-value highlight">{{ task.complete_user_num }}</span>
                        </div>
                        <div class="task-stat-item">
                            <span class="task-stat-label">任务时间</span>
                            <span class="task-stat-value">{{ formatTimestampMs(task.time) }}</span>
                        </div>
                        <div class="task-stat-item task-stat-item--full">
                            <span class="task-stat-label">考勤等级规则</span>
                            <div class="task-rule-row">
                                <span class="task-stat-value" :class="{ 'task-stat-value--warn': !hasAttendanceRule(task) }">
                                    {{ formatAttendanceRule(task) }}
                                </span>
                                <n-button size="tiny" quaternary @click="openRuleModal(task)">配置规则</n-button>
                            </div>
                        </div>
                    </div>

                    <div v-if="!hasAttendanceRule(task)" class="task-warning">
                        老任务尚未配置考勤等级规则，开始采集不受影响，但开始统计前必须先补齐规则。
                    </div>
                    <div v-if="Number(task.complete_user_num) > 0 || task.status === 1" class="task-warning task-warning--soft">
                        该任务已有统计结果。若编辑坐标或目标分组，系统不会自动删除旧战报，建议先清理战报后重新采集。
                    </div>

                    <div class="task-actions">
                        <n-button size="small" @click="getTaskDetail(task.id)">
                            <template #icon><Eye :size="14" /></template>
                            考勤详情
                        </n-button>
                        <n-button size="small" @click="openEditTask(task)" :disabled="isTaskBeingCaptured(task)">
                            <template #icon><Pencil :size="14" /></template>
                            编辑任务
                        </n-button>
                        <n-button type="info" size="small" @click="enableGetReport(task.id, task.pos)">
                            <template #icon><Play :size="14" /></template>
                            开始考勤
                        </n-button>
                        <n-popconfirm @positive-click="delTaskReport(task.id)" :show-icon="false">
                            <template #trigger>
                                <n-button type="warning" size="small">
                                    <template #icon><Eraser :size="14" /></template>
                                    清理战报
                                </n-button>
                            </template>
                            确认清理战报吗？数据删除后无法恢复。<br>清理战报可以减少统计考勤的耗时
                        </n-popconfirm>
                        <n-popconfirm @positive-click="delTask(task.id)" :show-icon="false">
                            <template #trigger>
                                <n-button type="error" size="small">
                                    <template #icon><Trash2 :size="14" /></template>
                                    删除任务
                                </n-button>
                            </template>
                            确认删除该任务吗？
                        </n-popconfirm>
                    </div>
                </div>
            </div>
            <n-empty v-else :description="searchKeyword ? '没有匹配的任务' : '暂无攻城任务'" style="padding: 60px 0;" />
        </n-card>
    </div>
</template>

<style scoped lang="scss">
.page-task {
    display: flex;
    flex-direction: column;
}

.page-card {
    border-radius: 12px;
}

.page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
}

.page-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--color-text);
    margin-bottom: 4px;
}

.page-desc {
    font-size: 13px;
    color: var(--color-text-secondary);
}

.toolbar-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
}

.search-input {
    max-width: 320px;
}

.default-rule-card {
    margin-bottom: 16px;
    padding: 16px;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-surface);
}

.default-rule-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 12px;
}

.default-rule-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text);
    margin-bottom: 4px;
}

.default-rule-desc {
    font-size: 12px;
    color: var(--color-text-secondary);
    line-height: 1.6;
}

.default-rule-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 16px;
}

.task-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.capture-status-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 20px;
    padding: 14px 16px;
    border: 1px solid var(--color-border);
    background: var(--color-bg);
    border-radius: 10px;
}

.capture-status-title {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin-bottom: 4px;
}

.capture-status-text {
    font-size: 14px;
    color: var(--color-text);
    font-weight: 500;
}

.task-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 10px;
    padding: 20px;
    transition: box-shadow 0.2s, transform 0.2s;

    &:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transform: translateY(-1px);
    }
}

.task-header {
    margin-bottom: 16px;
}

.task-title-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
}

.task-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--color-text);
}

.task-coords {
    font-size: 13px;
    color: var(--color-text-secondary);
}

.task-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px 24px;
    margin-bottom: 16px;
    padding: 16px;
    background: var(--color-bg);
    border-radius: 8px;
}

.task-stat-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.task-stat-item--full {
    grid-column: 1 / -1;
}

.task-stat-label {
    font-size: 12px;
    color: var(--color-text-secondary);
}

.task-stat-value {
    font-size: 14px;
    color: var(--color-text);
    font-weight: 500;

    &.highlight {
        color: var(--color-accent);
    }
}

.task-stat-value--warn {
    color: #d97706;
}

.task-stat-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.task-rule-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}

.task-warning {
    margin-bottom: 16px;
    padding: 10px 12px;
    border-radius: 8px;
    background: rgba(245, 158, 11, 0.12);
    color: var(--color-text);
    font-size: 12px;
    line-height: 1.5;
}

.task-warning--soft {
    background: var(--color-primary-light);
    color: var(--color-text);
}

.task-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.modal-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.group-select-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
}

.group-select-count {
    font-size: 12px;
    color: var(--color-text-secondary);
}

.report-modal {
    text-align: center;
}

.report-tip {
    font-size: 14px;
    color: var(--color-text-secondary);
    margin-bottom: 24px;
    line-height: 1.6;
}

.report-tip-secondary {
    margin-top: -8px;
    margin-bottom: 16px;
    font-size: 12px;
}

.report-counter {
    display: flex;
    justify-content: center;
    padding: 20px 0;
}

.report-mode-tag {
    margin-bottom: 16px;
}

.report-status-row {
    display: flex;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}

.rule-modal-tip {
    font-size: 13px;
    color: var(--color-text-secondary);
}

.detail-modal {
    overflow: auto;

    .detail-summary {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }

    .group-summary-section {
        margin-bottom: 16px;

        .group-summary-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--color-text-primary);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;

            &::before {
                content: '';
                display: inline-block;
                width: 4px;
                height: 14px;
                border-radius: 2px;
                background: var(--color-primary, #2080f0);
            }
        }
    }

    .detail-summary-item {
        padding: 12px;
        border: 1px solid var(--color-border);
        border-radius: 10px;
        background: var(--color-bg);
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .detail-summary-label {
        font-size: 12px;
        color: var(--color-text-secondary);
    }

    .detail-summary-value {
        font-size: 14px;
        color: var(--color-text);
        font-weight: 600;
    }

    :deep(.n-data-table-sorter) {
        opacity: 0;
        color: var(--color-primary);
        transition: opacity 0.15s;
    }

    :deep(th:hover .n-data-table-sorter) {
        opacity: 1;
    }

    :deep(.n-data-table-th--sorting .n-data-table-sorter) {
        opacity: 1;
        color: var(--color-primary);
    }
}

.summary-modal {
    overflow: hidden;
}

.summary-actions {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 16px;
}

@media (max-width: 768px) {
    .page-header {
        flex-direction: column;
        align-items: stretch;
    }

    .toolbar-row {
        flex-direction: column;
    }

    .search-input {
        max-width: none;
    }

    .task-stats {
        grid-template-columns: 1fr;
    }

    .default-rule-header {
        flex-direction: column;
        align-items: stretch;
    }

    .default-rule-grid {
        grid-template-columns: 1fr;
    }

    .group-select-toolbar {
        flex-direction: column;
        align-items: flex-start;
    }

    .detail-modal .detail-summary {
        grid-template-columns: 1fr;
    }
}
</style>
