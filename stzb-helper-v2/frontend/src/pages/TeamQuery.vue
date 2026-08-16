<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NCard, NButton, NInput, NEmpty, NSpin, NTag, NPagination, useMessage, NGrid, NGi, NPopconfirm, NModal, NForm, NFormItem, NSelect, NDivider } from 'naive-ui'
import { DeleteNameMapping, GetHiddenPlayerTeams, GetMaterializedStatsStatus, GetNameMappings, GetPlayerTeam, GetPlayerTeamExport, GetPlayerTeamRelatedBattles, HidePlayerTeam, RebuildMaterializedStats, RestoreHiddenPlayerTeam, SaveNameMapping } from '../../wailsjs/go/main/App'
import { Download, RefreshCw, Search, Swords, Star, ScrollText, EyeOff, RotateCcw, Settings } from 'lucide-vue-next'
import { herocfg, skillcfg, gear_cfg } from '../cfg'
import { buildNameMappingIndex, getMappedName, mergeHeroMapWithMappings, mergeSkillMapWithMappings } from '../utils/nameMappings.js'

const heroMap = JSON.parse(herocfg)
const skillMap = JSON.parse(skillcfg)
const gearMap: Record<number, any> = {}
gear_cfg.forEach((g: any) => { gearMap[g.gear_id] = g })

const nmessage = useMessage()
const loading = ref(false)
const results = ref<any[]>([])
const nameMappings = ref<any[]>([])
const mappingIndex = computed(() => buildNameMappingIndex(nameMappings.value))
const mappedHeroMap = computed(() => mergeHeroMapWithMappings(heroMap, mappingIndex.value))
const mappedSkillMap = computed(() => mergeSkillMapWithMappings(skillMap, mappingIndex.value))

const searchName = ref('')
const searchUnion = ref('')
const searchIdu = ref('')

const hasSearched = ref(false)
const viewMode = ref('list') // list | compact
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const queryMs = ref<number | null>(null)
const cacheHit = ref(false)
const source = ref('')
const statsReady = ref(false)
const rebuilding = ref(false)
const rebuildProgressText = ref('')
const relatedBattles = ref<Record<string, { loading: boolean, expanded: boolean, fetched: boolean, list: any[], total: number }>>({})
const hidingKeys = ref<Record<string, boolean>>({})
const hiddenModalVisible = ref(false)
const hiddenLoading = ref(false)
const hiddenRows = ref<any[]>([])
const hiddenPage = ref(1)
const hiddenPageSize = ref(10)
const hiddenTotal = ref(0)
const restoringHiddenKeys = ref<Record<string, boolean>>({})
let statsPollTimer: number | undefined

const doSearch = (newPage?: number) => {
    if (typeof newPage === 'number') page.value = newPage
    else page.value = 1
    loading.value = true
    results.value = []
    relatedBattles.value = {}
    hasSearched.value = true
    GetPlayerTeam(searchName.value, searchUnion.value, searchIdu.value, page.value, pageSize.value).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            results.value = (resp.data.list || []).map(prepareTeamDisplay)
            total.value = resp.data.total || 0
            queryMs.value = resp.data.query_ms ?? null
            cacheHit.value = !!resp.data.cache_hit
            source.value = resp.data.source || ''
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('查询失败: ' + e)
    }).finally(() => {
        loading.value = false
    })
}

const refreshStatsStatus = async () => {
    try {
        const resp = JSON.parse(await GetMaterializedStatsStatus())
        if (resp.code !== 200) {
            statsReady.value = false
            return
        }
        const wasRebuilding = rebuilding.value
        const states = resp.data.states || []
        const active = states.find(s => s.status === 'building') || states[0]
        const isBuilding = !!resp.data.rebuilding || states.some(s => s.status === 'building')
        statsReady.value = !!resp.data.team_ready
        rebuilding.value = isBuilding
        rebuildProgressText.value = formatRebuildProgress(active)
        if (isBuilding) {
            startStatsPolling()
        } else {
            stopStatsPolling()
            if (wasRebuilding && hasSearched.value) doSearch(page.value)
        }
    } catch {
        statsReady.value = false
        rebuilding.value = false
        stopStatsPolling()
    }
}

const rebuildStats = async () => {
    rebuilding.value = true
    rebuildProgressText.value = '准备重建...'
    try {
        const resp = JSON.parse(await RebuildMaterializedStats())
        if (resp.code === 200) {
            nmessage.success(resp.msg || '统计索引已开始后台重建')
            await refreshStatsStatus()
            startStatsPolling()
        } else {
            nmessage.error(resp.msg)
            rebuilding.value = false
        }
    } catch (e) {
        nmessage.error('重建失败: ' + e)
        rebuilding.value = false
    }
}

const formatRebuildProgress = (state) => {
    if (!state || state.status !== 'building') return ''
    const total = Number(state.battle_report_count || 0)
    const processed = Number(state.processed_report_count || 0)
    if (total <= 0) return '重建中...'
    const percent = Math.min(100, Math.floor(processed / total * 100))
    return `重建中 ${processed}/${total} (${percent}%)`
}

const startStatsPolling = () => {
    if (statsPollTimer) return
    statsPollTimer = window.setInterval(refreshStatsStatus, 1000)
}

const stopStatsPolling = () => {
    if (!statsPollTimer) return
    window.clearInterval(statsPollTimer)
    statsPollTimer = undefined
}

const teamKey = (team) => `${team.player_name}|${team.role}|${team.idu}|${team.hero1_id}|${team.hero2_id}|${team.hero3_id}`

const prepareTeamDisplay = (team) => ({
    ...team,
    parsed_skill_info: parseSkillInfo(team.all_skill_info, team.role),
})

const groupedPlayerTeams = computed(() => {
    const map: Record<string, any[]> = {}
    results.value.forEach(r => {
        if (!map[r.player_name]) {
            map[r.player_name] = []
        }
        map[r.player_name].push(r)
    })
    return map
})

const hideTeam = async (team) => {
    const key = teamKey(team)
    hidingKeys.value = { ...hidingKeys.value, [key]: true }
    try {
        const resp = JSON.parse(await HidePlayerTeam(
            team.player_name,
            team.role,
            team.idu || '',
            team.hero1_id,
            team.hero2_id,
            team.hero3_id,
            team.all_skill_info || '',
        ))
        if (resp.code === 200) {
            nmessage.success(resp.msg || '已隐藏该队伍，原始战报未被删除')
            results.value = results.value.filter(item => teamKey(item) !== key)
            total.value = Math.max(0, total.value - 1)
            const nextBattles = { ...relatedBattles.value }
            delete nextBattles[key]
            relatedBattles.value = nextBattles
            if (results.value.length === 0 && total.value > 0) doSearch(page.value)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('隐藏失败: ' + e)
    } finally {
        const next = { ...hidingKeys.value }
        delete next[key]
        hidingKeys.value = next
    }
}

const toggleRelatedBattles = async (team) => {
    const key = teamKey(team)
    const current = relatedBattles.value[key]
    if (current?.fetched) {
        relatedBattles.value[key] = { ...current, expanded: !current.expanded }
        return
    }
    relatedBattles.value[key] = { loading: true, expanded: true, fetched: false, list: current?.list || [], total: current?.total || 0 }
    try {
        const resp = JSON.parse(await GetPlayerTeamRelatedBattles(team.player_name, team.role, team.idu || '', team.hero1_id, team.hero2_id, team.hero3_id, 1, 20))
        if (resp.code === 200) {
            relatedBattles.value[key] = { loading: false, expanded: true, fetched: true, list: resp.data.list || [], total: resp.data.total || 0 }
        } else {
            relatedBattles.value[key] = { loading: false, expanded: false, fetched: false, list: [], total: 0 }
            nmessage.error(resp.msg)
        }
    } catch (e) {
        relatedBattles.value[key] = { loading: false, expanded: false, fetched: false, list: [], total: 0 }
        nmessage.error('战报加载失败: ' + e)
    }
}

const openHiddenManager = async () => {
    hiddenModalVisible.value = true
    hiddenPage.value = 1
    await loadHiddenTeams()
}

const loadHiddenTeams = async (newPage?: number) => {
    if (typeof newPage === 'number') hiddenPage.value = newPage
    hiddenLoading.value = true
    try {
        const resp = JSON.parse(await GetHiddenPlayerTeams(hiddenPage.value, hiddenPageSize.value))
        if (resp.code === 200) {
            hiddenRows.value = resp.data.list || []
            hiddenTotal.value = resp.data.total || 0
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('隐藏列表加载失败: ' + e)
    } finally {
        hiddenLoading.value = false
    }
}

const restoreHiddenTeam = async (row) => {
    const key = String(row.id)
    restoringHiddenKeys.value = { ...restoringHiddenKeys.value, [key]: true }
    try {
        const resp = JSON.parse(await RestoreHiddenPlayerTeam(row.id))
        if (resp.code === 200) {
            nmessage.success(resp.msg || '已恢复该队伍，原始战报未被删除')
            await loadHiddenTeams(hiddenPage.value)
            if (hasSearched.value) doSearch(page.value)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('恢复失败: ' + e)
    } finally {
        const next = { ...restoringHiddenKeys.value }
        delete next[key]
        restoringHiddenKeys.value = next
    }
}

const resultType = (label) => {
    if (label === '胜') return 'success'
    if (label === '负') return 'error'
    if (label === '平') return 'warning'
    return 'default'
}

const exporting = ref(false)
const doExport = async () => {
    exporting.value = true

    let allList = []

    try {
        const v = await GetPlayerTeamExport(searchName.value, searchUnion.value, searchIdu.value)
        const resp = JSON.parse(v)
        if (resp.code != 200) {
            nmessage.error(resp.msg)
            exporting.value = false
            return
        }
        allList = resp.data.list || []

        if (allList.length === 0) {
            nmessage.warning('没有数据可导出')
            exporting.value = false
            return
        }
        const XLSX = await import('xlsx')

        // 获取武将完整信息：红度\n等级\n名字-国家-兵种
        const getHeroInfo = (id, star, level) => {
            if (!id) return ''
            const hero = heroMap[String(resolveHeroId(id))]
            const name = hero ? `${hero.name}-${hero.country}-${hero.type}` : `ID:${id}`
            return `${star}红\n${level}级\n${name}`
        }

        // 获取技能信息：战法名 等级\n战法名 等级\n战法名 等级
        const getSkillInfo = (skills) => {
            if (!skills || skills.length === 0) return ''
            return skills.map(s => {
                const name = getSkillName(s.id)
                return name ? `${name} ${s.level}级` : ''
            }).filter(Boolean).join('\n')
        }

        // 生成xlsx数据
        const header = ['名字', '阵容红度', '大营武将', '中军武将', '前锋武将', '大营技能', '中军技能', '前锋技能', '大营宝物', '中军宝物', '前锋宝物', '记录类型', '记录时间']
        const rows = allList.map(r => {
            const hero1Info = getHeroInfo(r.hero1_id, r.hero1_star, r.hero1_level)
            const hero2Info = getHeroInfo(r.hero2_id, r.hero2_star, r.hero2_level)
            const hero3Info = getHeroInfo(r.hero3_id, r.hero3_star, r.hero3_level)
            const skills = parseSkillInfo(r.all_skill_info, r.role)
            const skill1Info = getSkillInfo(skills[0]?.skills)
            const skill2Info = getSkillInfo(skills[1]?.skills)
            const skill3Info = getSkillInfo(skills[2]?.skills)
            const gears = parseGearInfo(r.gear, r.role)
            const gear1Info = gears[0] ? `${gears[0].name} Lv.${gears[0].level}` : ''
            const gear2Info = gears[1] ? `${gears[1].name} Lv.${gears[1].level}` : ''
            const gear3Info = gears[2] ? `${gears[2].name} Lv.${gears[2].level}` : ''
            const role = r.role === 'attack' ? '攻击时记录' : '防守时记录'
            const time = formatTime(r.time)
            return [r.player_name, r.total_star, hero1Info, hero2Info, hero3Info,
                skill1Info, skill2Info, skill3Info, gear1Info, gear2Info, gear3Info, role, time]
        })

        // 创建xlsx
        const ws = XLSX.utils.aoa_to_sheet([header, ...rows])

        // 设置列宽
        ws['!cols'] = [
            { wch: 14 }, // 名字
            { wch: 8 },  // 阵容红度
            { wch: 18 }, // 大营武将
            { wch: 18 }, // 中军武将
            { wch: 18 }, // 前锋武将
            { wch: 22 }, // 大营技能
            { wch: 22 }, // 中军技能
            { wch: 22 }, // 前锋技能
            { wch: 16 }, // 大营宝物
            { wch: 16 }, // 中军宝物
            { wch: 16 }, // 前锋宝物
            { wch: 12 }, // 记录类型
            { wch: 18 }, // 记录时间
        ]

        const wb = XLSX.utils.book_new()
        XLSX.utils.book_append_sheet(wb, ws, '队伍数据')
        XLSX.writeFile(wb, `player_team_export_${new Date().toISOString().slice(0,10)}.xlsx`)

        const cost = resp.data.query_ms != null ? `，查询耗时 ${resp.data.query_ms}ms` : ''
        const hit = resp.data.cache_hit ? '，命中缓存' : ''
        nmessage.success(`已导出 ${allList.length} 条队伍数据${cost}${hit}`)
    } catch (e) {
        nmessage.error('导出失败: ' + e)
    } finally {
        exporting.value = false
    }
}

const resolveHeroId = (id) => {
    if (!id) return id
    const num = Number(id)
    return num >= 130000 ? num - 30000 : num
}

const getHeroName = (id) => {
    if (!id) return ''
    const mapped = getMappedName(mappingIndex.value, 'hero', id)
    if (mapped) return mapped
    const hero = mappedHeroMap.value[String(resolveHeroId(id))]
    return hero ? hero.name : `ID:${id}`
}

const getHeroCountry = (id) => {
    if (!id) return ''
    const hero = mappedHeroMap.value[String(resolveHeroId(id))]
    return hero ? hero.country : ''
}

const getHeroType = (id) => {
    if (!id) return ''
    const hero = mappedHeroMap.value[String(resolveHeroId(id))]
    return hero ? hero.type : ''
}

const getHeroIcon = (id) => {
    if (!id) return id
    const hero = mappedHeroMap.value[String(resolveHeroId(id))]
    return hero ? hero.iconId : id
}

const getSkillName = (id) => {
    if (!id) return ''
    const mapped = getMappedName(mappingIndex.value, 'skill', id)
    if (mapped) return mapped
    const skill = mappedSkillMap.value[String(id)]
    return skill ? skill.name : ''
}

const getSkillQuality = (id) => {
    if (!id) return ''
    const skill = mappedSkillMap.value[String(id)]
    return skill ? skill.zfQuality : ''
}

const parseSkillInfo = (str, role) => {
    if (!str) return []
    let groups = String(str).split(';').filter(s => s.trim() !== '')
    let parsed = groups.map(g => {
        const parts = g.split(',')
        return {
            heroIndex: parseInt(parts[0]),
            skills: [
                { id: parts[1], level: parseInt(parts[2]) },
                { id: parts[3], level: parseInt(parts[4]) },
                { id: parts[5], level: parseInt(parts[6]) },
            ].filter(s => s.id && s.id !== '0')
        }
    })
    if (role === 'defend') {
        parsed = parsed.filter(g => g.heroIndex >= 4).reverse()
    } else {
        parsed = parsed.filter(g => g.heroIndex <= 3)
    }
    return parsed
}

const formatTime = (ts) => {
    if (!ts) return ''
    const d = new Date(ts * 1000)
    const pad = (n) => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const roleLabel = (role) => role === 'attack' ? '攻' : '守'
const roleType = (role) => role === 'attack' ? 'error' : 'info'

const qualityColor = (q) => {
    if (q === 'S') return '#f59e0b'
    if (q === 'A') return '#3b82f6'
    if (q === 'B') return '#10b981'
    return '#9ca3af'
}

const hasBuiltInHeroName = (id) => !!mappedHeroMap.value[String(resolveHeroId(id))]
const hasBuiltInSkillName = (id) => !!mappedSkillMap.value[String(id)]
const hasBuiltInGearName = (id) => !!gearMap[Number(id)]
const hasMappedName = (kind, id) => !!getMappedName(mappingIndex.value, kind, id)

const unknownNameItems = computed(() => {
    const seen = new Set<string>()
    const items: any[] = []
    const add = (kind: string, id: number | string) => {
        const num = Number(id)
        if (!num) return
        const key = `${kind}-${num}`
        if (seen.has(key) || hasMappedName(kind, num)) return
        if (kind === 'hero' && hasBuiltInHeroName(num)) return
        if (kind === 'skill' && hasBuiltInSkillName(num)) return
        if (kind === 'gear' && hasBuiltInGearName(num)) return
        seen.add(key)
        items.push({ kind, id: num })
    }
    results.value.forEach(team => {
        add('hero', team.hero1_id)
        add('hero', team.hero2_id)
        add('hero', team.hero3_id)
        parseSkillInfo(team.all_skill_info, team.role).forEach(group => {
            (group.skills || []).forEach((skill: any) => add('skill', skill.id))
        })
        parseGearInfo(team.gear, team.role).filter(Boolean).forEach((g: any) => add('gear', g.id))
    })
    return items
})

const parseGearInfo = (gearStr, role) => {
    if (!gearStr) return [null, null, null]
    const slots = String(gearStr).split(';').filter(s => s.trim() !== '')
    let parsed = []
    for (let i = 0; i < slots.length; i++) {
        const parts = slots[i].split(',')
        if (parts.length !== 3) continue
        const gearId = parseInt(parts[0])
        const level = parseInt(parts[1])
        const rawHeroIndex = parseInt(parts[2])
        const heroIndex = rawHeroIndex >= 1 && rawHeroIndex <= 6
            ? rawHeroIndex
            : (role === 'defend' ? i + 4 : i + 1)
        if (gearId === 0) {
            parsed.push({ heroIndex, gear: null })
        } else {
            const mapped = getMappedName(mappingIndex.value, 'gear', gearId)
            const gear = gearMap[gearId]
            parsed.push({ heroIndex, gear: { id: gearId, name: mapped || (gear ? gear.name : `ID:${gearId}`), level } })
        }
    }
    if (role === 'defend') {
        parsed = parsed.filter(g => g.heroIndex >= 4).reverse()
    } else {
        parsed = parsed.filter(g => g.heroIndex <= 3)
    }
    return [0, 1, 2].map(i => parsed[i]?.gear || null)
}

const getGearDisplay = (gearStr, role, index) => {
    const gears = parseGearInfo(gearStr, role)
    const g = gears[index]
    if (!g) return ''
    return `${g.name} Lv.${g.level}`
}

const loadNameMappings = async (silent = false) => {
    try {
        const res = await GetNameMappings()
        const resp = JSON.parse(res)
        if (resp.code == 200) {
            nameMappings.value = resp.data || []
        }
    } catch (e) {
        if (!silent) nmessage.error('加载名称映射失败: ' + e)
    }
}

const mappingModalVisible = ref(false)
const mappingForm = ref({ kind: 'hero', id: null as number | null, name: '' })
const savingMapping = ref(false)
const mappingLoading = ref(false)
const mappingKindOptions = [
    { label: '武将', value: 'hero' },
    { label: '战法', value: 'skill' },
    { label: '宝物', value: 'gear' },
]
const mappingKindLabel = (kind) => mappingKindOptions.find(o => o.value === kind)?.label || kind

const fillMappingForm = (item: any) => {
    mappingForm.value = {
        kind: item.kind || 'hero',
        id: Number(item.id || 0),
        name: item.name || '',
    }
}
const filteredNameMappings = computed(() =>
    nameMappings.value.filter(row => row.kind === mappingForm.value.kind)
)

const openNameMappingManager = async () => {
    mappingModalVisible.value = true
    mappingLoading.value = true
    await loadNameMappings()
    mappingLoading.value = false
}

const saveNameMapping = async () => {
    const id = Number(mappingForm.value.id)
    const name = mappingForm.value.name.trim()
    if (!id || !name) {
        nmessage.warning('请输入 ID 和名称')
        return
    }
    savingMapping.value = true
    try {
        const payload = { kind: mappingForm.value.kind, id, name }
        const res = await SaveNameMapping(JSON.stringify(payload))
        const resp = JSON.parse(res)
        if (resp.code == 200) {
            nmessage.success(resp.msg || '保存成功')
            mappingForm.value.id = null
            mappingForm.value.name = ''
            await loadNameMappings(true)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('保存失败: ' + e)
    } finally {
        savingMapping.value = false
    }
}

const deleteNameMapping = async (row: any) => {
    try {
        const res = await DeleteNameMapping(row.kind, Number(row.id))
        const resp = JSON.parse(res)
        if (resp.code == 200) {
            nmessage.success(resp.msg || '已删除')
            await loadNameMappings(true)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('删除失败: ' + e)
    }
}

onMounted(async () => {
    await refreshStatsStatus()
    if (rebuilding.value) startStatsPolling()
    await loadNameMappings(true)
})
onUnmounted(stopStatsPolling)
</script>

<template>
    <div class="team-query">
        <div class="query-header">
            <h2 class="query-title">
                <Swords :size="20" />
                队伍查询
            </h2>
            <p class="query-desc">查询玩家队伍配置与战法</p>
        </div>

        <div class="search-box">
            <n-input v-model:value="searchName" placeholder="玩家名称" clearable @keyup.enter="doSearch()" />
            <n-input v-model:value="searchUnion" placeholder="同盟" clearable @keyup.enter="doSearch()" />
            <n-input v-model:value="searchIdu" placeholder="队伍ID" clearable @keyup.enter="doSearch()" />
            <n-button type="primary" @click="doSearch()" :loading="loading">
                <template #icon><Search :size="16" /></template>
                查询
            </n-button>
            <n-button @click="doExport()" :loading="exporting">
                <template #icon><Download :size="16" /></template>
                导出Excel
            </n-button>
            <n-button @click="rebuildStats()" :loading="rebuilding">
                <template #icon><RefreshCw :size="16" /></template>
                重建索引
            </n-button>
            <n-button @click="openHiddenManager()">
                <template #icon><EyeOff :size="16" /></template>
                隐藏管理
            </n-button>
            <n-button @click="openNameMappingManager()">
                <template #icon><Settings :size="16" /></template>
                名称映射
            </n-button>
            <div class="view-toggle">
                <n-button-group size="small">
                    <n-button :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'">列表</n-button>
                    <n-button :type="viewMode === 'compact' ? 'primary' : 'default'" @click="viewMode = 'compact'">紧凑</n-button>
                </n-button-group>
            </div>
        </div>

        <div v-if="total > pageSize" class="pagination">
            <n-pagination v-model:page="page" :page-size="pageSize" :item-count="total" :on-update:page="doSearch" />
        </div>

        <div v-if="loading" class="loading">
            <n-spin size="medium" />
            <span>查询中...</span>
        </div>

        <n-empty v-else-if="hasSearched && results.length === 0" description="未找到队伍数据" class="empty" />

        <div v-else-if="results.length > 0" class="results">
            <div class="result-stats">
                <span>{{ Object.keys(groupedPlayerTeams).length }} 位玩家</span>
                <span>{{ results.length }} 支队伍</span>
                <span>共 {{ total }} 条</span>
                <span v-if="queryMs !== null">耗时 {{ queryMs }}ms</span>
                <span v-if="cacheHit">命中缓存</span>
                <span v-if="source === 'materialized'">统计索引</span>
                <span v-else-if="source === 'raw'">原始查询</span>
                <span v-if="!statsReady">索引未就绪</span>
                <span v-if="rebuildProgressText">{{ rebuildProgressText }}</span>
            </div>

            <!-- 紧凑模式 - 表格视图 -->
            <div v-if="viewMode === 'compact'" class="compact-view">
                <table class="team-table">
                    <thead>
                        <tr>
                            <th>玩家</th>
                            <th>队伍 (大营→中军→前锋)</th>
                            <th>宝物</th>
                            <th>红度</th>
                            <th>角色</th>
                            <th>时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="team in results" :key="team.battle_id + team.role">
                            <tr>
                                <td class="player-cell">
                                    <span class="player-name">{{ team.player_name }}</span>
                                    <span class="player-idu">ID:{{ team.idu }}</span>
                                </td>
                                <td class="team-cell">
                                    <div class="hero-mini">
                                        <img v-if="team.hero1_id" :src="`https://g0.gph.netease.com/ngsocial/community/stzb/cn/cards/cut/card_small_${getHeroIcon(team.hero1_id)}.jpg?gameid=g10`" @error="($event.target as any).style.display='none'" />
                                        <span class="hero-mini-name">{{ getHeroName(team.hero1_id) }}<span class="hero-mini-type">{{ getHeroType(team.hero1_id) }}</span></span>
                                    </div>
                                    <span class="team-arrow">→</span>
                                    <div class="hero-mini">
                                        <img v-if="team.hero2_id" :src="`https://g0.gph.netease.com/ngsocial/community/stzb/cn/cards/cut/card_small_${getHeroIcon(team.hero2_id)}.jpg?gameid=g10`" @error="($event.target as any).style.display='none'" />
                                        <span class="hero-mini-name">{{ getHeroName(team.hero2_id) }}<span class="hero-mini-type">{{ getHeroType(team.hero2_id) }}</span></span>
                                    </div>
                                    <span class="team-arrow">→</span>
                                    <div class="hero-mini">
                                        <img v-if="team.hero3_id" :src="`https://g0.gph.netease.com/ngsocial/community/stzb/cn/cards/cut/card_small_${getHeroIcon(team.hero3_id)}.jpg?gameid=g10`" @error="($event.target as any).style.display='none'" />
                                        <span class="hero-mini-name">{{ getHeroName(team.hero3_id) }}<span class="hero-mini-type">{{ getHeroType(team.hero3_id) }}</span></span>
                                    </div>
                                </td>
                                <td class="gear-cell">
                                    <div v-for="(g, gi) in parseGearInfo(team.gear, team.role)" :key="gi" class="gear-item">
                                        <span v-if="g" class="gear-name">{{ g.name }} <span class="gear-level">Lv.{{ g.level }}</span></span>
                                        <span v-else class="gear-empty">-</span>
                                    </div>
                                </td>
                                <td class="star-cell">
                                    <span class="star-value">{{ team.total_star }}</span>
                                </td>
                                <td class="role-cell">
                                    <n-tag :type="roleType(team.role)" size="small" :bordered="false">{{ roleLabel(team.role) }}</n-tag>
                                </td>
                                <td class="time-cell">{{ formatTime(team.time) }}</td>
                                <td>
                                    <div class="action-cell">
                                        <n-button size="tiny" quaternary @click="toggleRelatedBattles(team)">
                                            <template #icon><ScrollText :size="14" /></template>
                                            战报
                                        </n-button>
                                        <n-popconfirm @positive-click="hideTeam(team)">
                                            <template #trigger>
                                                <n-button size="tiny" quaternary type="warning" :loading="!!hidingKeys[teamKey(team)]">
                                                    <template #icon><EyeOff :size="14" /></template>
                                                    隐藏
                                                </n-button>
                                            </template>
                                            隐藏后队伍查询和胜率查询都会排除这支队伍，确定吗？
                                        </n-popconfirm>
                                    </div>
                                </td>
                            </tr>
                            <tr v-if="relatedBattles[teamKey(team)]?.expanded || relatedBattles[teamKey(team)]?.loading">
                                <td colspan="6">
                                    <div class="related-battles">
                                        <div v-if="relatedBattles[teamKey(team)]?.loading" class="related-loading">加载中...</div>
                                        <div v-else class="related-list">
                                            <div class="related-item" v-for="battle in relatedBattles[teamKey(team)]?.list || []" :key="battle.battle_id">
                                                <n-tag size="tiny" :type="resultType(battle.result_label)" :bordered="false">{{ battle.result_label }}</n-tag>
                                                <span>{{ formatTime(battle.time) }}</span>
                                                <span>对手 {{ battle.opponent_name || '-' }}</span>
                                                <span>{{ battle.attack_hp }} / {{ battle.defend_hp }}</span>
                                            </div>
                                        </div>
                                    </div>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>

            <!-- 列表模式 - 卡片视图 -->
            <div v-else class="list-view">
                <div class="player-group" v-for="(teams, playerName) in groupedPlayerTeams" :key="playerName">
                    <div class="player-header">
                        <span class="player-title">{{ playerName }}</span>
                        <span class="player-count">{{ teams.length }} 支队伍</span>
                    </div>
                    <div class="team-list">
                        <div class="team-item" v-for="team in teams" :key="team.battle_id + team.role">
                            <div class="team-meta">
                                <n-tag :type="roleType(team.role)" size="tiny" :bordered="false">{{ roleLabel(team.role) }}</n-tag>
                                <span class="team-idu">ID {{ team.idu }}</span>
                                <span class="team-star"><Star :size="12" /> {{ team.total_star }}红</span>
                                <span class="team-time">{{ formatTime(team.time) }}</span>
                                <n-button size="tiny" quaternary @click="toggleRelatedBattles(team)">
                                    <template #icon><ScrollText :size="14" /></template>
                                    战报
                                </n-button>
                                <n-popconfirm @positive-click="hideTeam(team)">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary type="warning" :loading="!!hidingKeys[teamKey(team)]">
                                            <template #icon><EyeOff :size="14" /></template>
                                            隐藏
                                        </n-button>
                                    </template>
                                    隐藏后队伍查询和胜率查询都会排除这支队伍，确定吗？
                                </n-popconfirm>
                            </div>
                            <div class="team-heroes">
                                <div class="hero-card" v-for="i in 3" :key="i">
                                    <div class="hero-main">
                                        <img v-if="team[`hero${i}_id`]" :src="`https://g0.gph.netease.com/ngsocial/community/stzb/cn/cards/cut/card_small_${getHeroIcon(team[`hero${i}_id`])}.jpg?gameid=g10`" @error="($event.target as any).style.display='none'" />
                                        <span class="hero-name">{{ getHeroName(team[`hero${i}_id`]) }}</span>
                                        <span class="hero-type">{{ getHeroType(team[`hero${i}_id`]) }}</span>
                                        <span class="hero-level">Lv.{{ team[`hero${i}_level`] }}</span>
                                    </div>
                                    <div v-if="team.all_skill_info" class="hero-skills">
                                        <span v-for="(skill, si) in (team.parsed_skill_info?.[i-1]?.skills || [])" :key="si" class="skill-tag" :style="{ borderColor: qualityColor(getSkillQuality(skill.id)) }">
                                            {{ getSkillName(skill.id) }}
                                        </span>
                                    </div>
                                    <div v-if="getGearDisplay(team.gear, team.role, i-1)" class="hero-gear">
                                        <span class="gear-tag">{{ getGearDisplay(team.gear, team.role, i-1) }}</span>
                                    </div>
                                </div>
                            </div>
                            <div v-if="relatedBattles[teamKey(team)]?.expanded || relatedBattles[teamKey(team)]?.loading" class="related-battles">
                                <div v-if="relatedBattles[teamKey(team)]?.loading" class="related-loading">加载中...</div>
                                <div v-else class="related-list">
                                    <div class="related-item" v-for="battle in relatedBattles[teamKey(team)]?.list || []" :key="battle.battle_id">
                                        <n-tag size="tiny" :type="resultType(battle.result_label)" :bordered="false">{{ battle.result_label }}</n-tag>
                                        <span>{{ formatTime(battle.time) }}</span>
                                        <span>对手 {{ battle.opponent_name || '-' }}</span>
                                        <span>兵力 {{ battle.attack_hp }} / {{ battle.defend_hp }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <n-modal v-model:show="mappingModalVisible" preset="card" title="名称映射管理" class="mapping-modal" style="width: min(600px, calc(100vw - 48px))" to="body">
            <div class="mapping-form">
                <n-form inline>
                    <n-form-item label="类型">
                        <n-select v-model:value="mappingForm.kind" :options="mappingKindOptions" style="width: 140px" />
                    </n-form-item>
                    <n-form-item label="ID">
                        <n-input-number v-model:value="mappingForm.id" placeholder="原ID" style="width: 160px" :show-button="false" />
                    </n-form-item>
                    <n-form-item label="名称">
                        <n-input v-model:value="mappingForm.name" placeholder="自定义名称" style="width: 160px" />
                    </n-form-item>
                    <n-form-item>
                        <n-button type="primary" :loading="savingMapping" @click="saveNameMapping">保存映射</n-button>
                    </n-form-item>
                </n-form>
            </div>

            <n-divider>当前结果中的未知 ID</n-divider>
            <div v-if="unknownNameItems.length === 0" class="mapping-empty">当前查询结果里没有未知 ID</div>
            <div v-else class="unknown-id-list">
                <n-button
                    v-for="item in unknownNameItems"
                    :key="`${item.kind}-${item.id}`"
                    size="small"
                    secondary
                    @click="fillMappingForm(item)"
                >
                    {{ mappingKindLabel(item.kind) }} {{ item.id }}
                </n-button>
            </div>

            <n-divider>已保存映射</n-divider>
            <div v-if="mappingLoading" class="mapping-loading">
                <n-spin size="small" />
                <span>读取中...</span>
            </div>
            <n-empty v-else-if="filteredNameMappings.length === 0" description="当前类型暂无映射" />
            <div v-else class="mapping-list">
                <div class="mapping-row" v-for="row in filteredNameMappings" :key="`${row.kind}-${row.id}`">
                    <div class="mapping-row-info">
                        <n-tag size="small" :bordered="false">{{ mappingKindLabel(row.kind) }}</n-tag>
                        <span class="mapping-id">ID {{ row.id }}</span>
                        <strong class="mapping-name">{{ row.name }}</strong>
                    </div>
                    <div class="mapping-row-actions">
                        <n-button size="tiny" quaternary @click="fillMappingForm(row)">编辑</n-button>
                        <n-popconfirm @positive-click="deleteNameMapping(row)">
                            <template #trigger>
                                <n-button size="tiny" quaternary type="error">删除</n-button>
                            </template>
                            确认删除该映射？
                        </n-popconfirm>
                    </div>
                </div>
            </div>
        </n-modal>

        <n-modal v-model:show="hiddenModalVisible" preset="card" title="隐藏队伍管理" class="hidden-modal">
            <div class="hidden-manager">
                <div v-if="hiddenLoading" class="hidden-loading">
                    <n-spin size="small" />
                    <span>加载中...</span>
                </div>
                <n-empty v-else-if="hiddenRows.length === 0" description="暂无隐藏队伍" />
                <div v-else class="hidden-list">
                    <div class="hidden-item" v-for="row in hiddenRows" :key="row.id">
                        <div class="hidden-main">
                            <div class="hidden-title">
                                <span>{{ row.player_name }}</span>
                                <n-tag :type="roleType(row.role)" size="tiny" :bordered="false">{{ roleLabel(row.role) }}</n-tag>
                                <span>ID {{ row.idu || '-' }}</span>
                            </div>
                            <div class="hidden-heroes">
                                {{ getHeroName(row.hero1_id) }} / {{ getHeroName(row.hero2_id) }} / {{ getHeroName(row.hero3_id) }}
                            </div>
                            <div class="hidden-time">{{ formatTime(row.created_at) }}</div>
                        </div>
                        <n-button size="small" quaternary type="primary" :loading="!!restoringHiddenKeys[String(row.id)]" @click="restoreHiddenTeam(row)">
                            <template #icon><RotateCcw :size="14" /></template>
                            恢复
                        </n-button>
                    </div>
                </div>
                <div v-if="hiddenTotal > hiddenPageSize" class="hidden-pagination">
                    <n-pagination v-model:page="hiddenPage" :page-size="hiddenPageSize" :item-count="hiddenTotal" :on-update:page="loadHiddenTeams" />
                </div>
            </div>
        </n-modal>
    </div>
</template>

<style scoped lang="scss">
.team-query {
    max-width: 1100px;
    margin: 0 auto;
}

.query-header {
    margin-bottom: 20px;

    .query-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 18px;
        font-weight: 600;
        margin: 0 0 4px;
        color: var(--color-text);
    }

    .query-desc {
        font-size: 13px;
        color: #999;
        margin: 0;
    }
}

.search-box {
    display: flex;
    gap: 10px;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .n-input {
        flex: 1;
        min-width: 120px;
    }

    .view-toggle {
        flex-shrink: 0;
    }
}

.pagination {
    display: flex;
    justify-content: center;
    margin-bottom: 16px;
}

.loading, .empty {
    padding: 60px 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    color: #999;
}

.results {
    .result-stats {
        display: flex;
        gap: 16px;
        padding: 12px 16px;
        background: var(--color-surface-hover);
        border-radius: 8px;
        margin-bottom: 16px;
        font-size: 13px;
        color: var(--color-text-secondary);
    }
}

// 紧凑表格模式
.compact-view {
    overflow-x: auto;

    .team-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;

        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #f0f0f0;
        }

        th {
            background: var(--color-surface-hover);
            font-weight: 500;
            color: var(--color-text-secondary);
        }

        tr:hover td {
            background: var(--color-surface-hover);
        }

        .player-cell {
            .player-name {
                font-weight: 500;
                color: var(--color-text);
            }
            .player-idu {
                display: block;
                font-size: 11px;
                color: #999;
            }
        }

        .team-cell {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .hero-mini {
            display: flex;
            align-items: center;
            gap: 4px;

            img {
                width: 24px;
                height: 24px;
                border-radius: 4px;
            }

            .hero-mini-name {
                font-size: 12px;
                color: var(--color-text-secondary);
            }

            .hero-mini-type {
                margin-left: 2px;
                font-size: 11px;
            }
        }

        .team-arrow {
            color: #ccc;
            font-size: 10px;
        }

        .star-cell .star-value {
            font-weight: 600;
            color: #f59e0b;
        }

        .gear-cell {
            font-size: 11px;

            .gear-item { margin-bottom: 2px; }
            .gear-name { color: #8b5cf6; }
            .gear-level { color: #999; font-size: 10px; }
            .gear-empty { color: #ddd; }
        }

        .role-cell .n-tag {
            font-size: 11px;
        }

        .time-cell {
            color: #999;
            font-size: 12px;
        }

        .action-cell {
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }
    }
}

.related-battles {
    margin-top: 10px;
    padding: 10px 12px;
    background: var(--color-surface);
    border: 1px solid #eee;
    border-radius: 6px;

    .related-loading {
        font-size: 12px;
        color: #999;
    }

    .related-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .related-item {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 12px;
        color: var(--color-text-secondary);
        flex-wrap: wrap;
    }
}

.mapping-modal {
    max-width: 640px;
}

.mapping-form {
    margin-bottom: 8px;
}

.mapping-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 32px 0;
    color: #999;
}

.mapping-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 300px;
    overflow-y: auto;
}

.mapping-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 12px;
    background: var(--color-surface-hover);
    border-radius: 6px;
    font-size: 13px;
}

.mapping-row-info {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
}

.mapping-row-actions {
    display: flex;
    align-items: center;
    gap: 4px;
}

.mapping-id {
    color: #999;
    min-width: 60px;
}

.mapping-name {
    color: var(--color-text);
}

.mapping-empty {
    text-align: center;
    color: #999;
    padding: 16px 0;
    font-size: 13px;
}

.unknown-id-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    max-height: 120px;
    overflow-y: auto;
}

.hidden-modal {
    max-width: 720px;
}

.hidden-manager {
    min-height: 160px;
}

.hidden-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 48px 0;
    color: #999;
}

.hidden-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.hidden-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px;
    border: 1px solid #eee;
    border-radius: 8px;
    background: var(--color-surface-hover);
}

.hidden-main {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.hidden-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text);
    flex-wrap: wrap;
}

.hidden-heroes {
    font-size: 13px;
    color: var(--color-text-secondary);
}

.hidden-time {
    font-size: 12px;
    color: #999;
}

.hidden-pagination {
    display: flex;
    justify-content: center;
    margin-top: 16px;
}

// 列表卡片模式
.list-view {
    .player-group {
        margin-bottom: 20px;
        background: var(--color-surface);
        border-radius: 10px;
        border: 1px solid #f0f0f0;
        overflow: hidden;
    }

    .player-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background: var(--color-surface-hover);
        border-bottom: 1px solid #f0f0f0;

        .player-title {
            font-weight: 600;
            color: var(--color-text);
        }

        .player-count {
            font-size: 12px;
            color: #999;
        }
    }

    .team-list {
        padding: 12px;
    }

    .team-item {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
        background: var(--color-surface-hover);

        &:last-child {
            margin-bottom: 0;
        }

        .team-meta {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;

            .team-idu {
                font-size: 12px;
                color: var(--color-text-secondary);
            }

            .team-star {
                display: flex;
                align-items: center;
                gap: 2px;
                font-size: 12px;
                color: #f59e0b;
            }

            .team-time {
                font-size: 12px;
                color: #999;
                margin-left: auto;
            }
        }

        .team-heroes {
            display: flex;
            gap: 12px;

            .hero-card {
                display: flex;
                flex-direction: column;
                gap: 6px;
                padding: 10px;
                background: var(--color-surface);
                border-radius: 6px;
                border: 1px solid #e8e8e8;
                flex: 1;

                .hero-main {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }

                img {
                    width: 32px;
                    height: 32px;
                    border-radius: 4px;
                }

                .hero-name {
                    font-size: 13px;
                    font-weight: 500;
                }

                .hero-type {
                    font-size: 11px;
                }

                .hero-level {
                    font-size: 11px;
                    color: #999;
                }

                .hero-skills {
                    display: flex;
                    flex-direction: column;
                    gap: 3px;

                    .skill-tag {
                        padding: 2px 8px;
                        font-size: 11px;
                        background: var(--color-surface-hover);
                        border: 1px solid;
                        border-radius: 4px;
                        color: var(--color-text-secondary);
                        white-space: nowrap;
                    }
                }

                .hero-gear {
                    .gear-tag {
                        display: inline-block;
                        padding: 2px 8px;
                        font-size: 11px;
                        background: rgba(139, 92, 246, 0.1);
                        border: 1px solid #8b5cf6;
                        border-radius: 4px;
                        color: #8b5cf6;
                        white-space: nowrap;
                    }
                }
            }
        }
    }
}
</style>
