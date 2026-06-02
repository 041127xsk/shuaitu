<script setup lang="ts">
import { computed, ref } from 'vue'
import {
    NButton,
    NButtonGroup,
    NDivider,
    NEmpty,
    NForm,
    NFormItem,
    NGi,
    NGrid,
    NInput,
    NInputNumber,
    NModal,
    NPagination,
    NPopconfirm,
    NSelect,
    NSpace,
    NSpin,
    NTag,
    useMessage
} from 'naive-ui'
import {
    CreateManualPlayerTeam,
    DeleteManualPlayerTeam,
    GetHiddenPlayerTeams,
    GetPlayerTeam,
    GetPlayerTeamExport,
    HidePlayerTeam,
    RestoreHiddenPlayerTeam,
    UpdateManualPlayerTeam
} from '../../wailsjs/go/main/App'
import { Download, EyeOff, Pencil, Plus, RotateCcw, Search, Settings, Star, Swords, Trash2 } from 'lucide-vue-next'
import { gear_cfg, herocfg, skillcfg } from '../cfg'

const heroMap = JSON.parse(herocfg)
const skillMap = JSON.parse(skillcfg)
const gearMap: Record<number, any> = {}
gear_cfg.forEach((g: any) => { gearMap[g.gear_id] = g })

const nmessage = useMessage()
const loading = ref(false)
const exporting = ref(false)
const savingTeam = ref(false)
const results = ref<any[]>([])

const searchName = ref('')
const searchUnion = ref('')
const searchIdu = ref('')
const hasSearched = ref(false)
const viewMode = ref('list')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const queryMs = ref<number | null>(null)
const cacheHit = ref(false)

const roleOptions = [
    { label: '进攻记录', value: 'attack' },
    { label: '防守记录', value: 'defend' }
]

const emptyTeamForm = () => ({
    id: 0,
    player_name: '',
    union_name: '',
    idu: '',
    role: 'attack',
    time: Math.floor(Date.now() / 1000),
    battle_id: 0,
    hero1_id: 0,
    hero2_id: 0,
    hero3_id: 0,
    hero1_level: 50,
    hero2_level: 50,
    hero3_level: 50,
    hero1_star: 0,
    hero2_star: 0,
    hero3_star: 0,
    total_star: 0,
    hp: 30000,
    all_skill_info: '',
    gear: '',
    hero_type: '',
    note: '',
    source_battle_id: 0,
    source_role: ''
})

const emptySkillRows = () => [1, 2, 3].map(() => ({
    main: 0,
    main_level: 10,
    skill1: 0,
    skill1_level: 10,
    skill2: 0,
    skill2_level: 10
}))

const teamModalVisible = ref(false)
const hiddenModalVisible = ref(false)
const hiddenLoading = ref(false)
const hiddenTeams = ref<any[]>([])
const formMode = ref<'create' | 'edit'>('create')
const teamForm = ref<any>(emptyTeamForm())
const skillRows = ref<any[]>(emptySkillRows())

const totalStarAuto = computed(() =>
    Number(teamForm.value.hero1_star || 0) + Number(teamForm.value.hero2_star || 0) + Number(teamForm.value.hero3_star || 0)
)

const doSearch = (newPage?: number) => {
    if (typeof newPage === 'number') page.value = newPage
    else page.value = 1
    loading.value = true
    results.value = []
    hasSearched.value = true
    GetPlayerTeam(searchName.value, searchUnion.value, searchIdu.value, page.value, pageSize.value).then(v => {
        const resp = JSON.parse(v)
        if (resp.code == 200) {
            results.value = resp.data.list || []
            total.value = resp.data.total || 0
            queryMs.value = resp.data.query_ms ?? null
            cacheHit.value = !!resp.data.cache_hit
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('查询失败: ' + e)
    }).finally(() => {
        loading.value = false
    })
}

const doExport = async () => {
    exporting.value = true
    try {
        const v = await GetPlayerTeamExport(searchName.value, searchUnion.value, searchIdu.value)
        const resp = JSON.parse(v)
        if (resp.code != 200) {
            nmessage.error(resp.msg)
            return
        }
        const allList = resp.data.list || []
        if (allList.length === 0) {
            nmessage.warning('没有数据可导出')
            return
        }

        const XLSX = await import('xlsx')
        const getHeroInfo = (id: number, star: number, level: number) => {
            if (!id) return ''
            const hero = heroMap[String(resolveHeroId(id))]
            const name = hero ? `${hero.name}-${hero.country}-${hero.type}` : `ID:${id}`
            return `${star}红\n${level}级\n${name}`
        }
        const getSkillInfo = (skills: any[]) => {
            if (!skills || skills.length === 0) return ''
            return skills.map(s => {
                const name = getSkillName(s.id)
                return name ? `${name} ${s.level}级` : ''
            }).filter(Boolean).join('\n')
        }

        const header = ['名字', '同盟', '队伍ID', '阵容红度', '大营武将', '中军武将', '前锋武将', '大营技能', '中军技能', '前锋技能', '大营宝物', '中军宝物', '前锋宝物', '记录类型', '来源', '记录时间']
        const rows = allList.map((r: any) => {
            const skills = parseSkillInfo(r.all_skill_info, r.role)
            const gears = parseGearInfo(r.gear, r.role)
            return [
                r.player_name,
                r.union_name || '',
                r.idu,
                r.total_star,
                getHeroInfo(r.hero1_id, r.hero1_star, r.hero1_level),
                getHeroInfo(r.hero2_id, r.hero2_star, r.hero2_level),
                getHeroInfo(r.hero3_id, r.hero3_star, r.hero3_level),
                getSkillInfo(skills[0]?.skills),
                getSkillInfo(skills[1]?.skills),
                getSkillInfo(skills[2]?.skills),
                gears[0] ? `${gears[0].name} Lv.${gears[0].level}` : '',
                gears[1] ? `${gears[1].name} Lv.${gears[1].level}` : '',
                gears[2] ? `${gears[2].name} Lv.${gears[2].level}` : '',
                r.role === 'attack' ? '攻击时记录' : '防守时记录',
                r.manual ? '手工修正' : '原始战报',
                formatTime(r.time)
            ]
        })

        const ws = XLSX.utils.aoa_to_sheet([header, ...rows])
        ws['!cols'] = [
            { wch: 14 }, { wch: 12 }, { wch: 12 }, { wch: 8 },
            { wch: 18 }, { wch: 18 }, { wch: 18 },
            { wch: 22 }, { wch: 22 }, { wch: 22 },
            { wch: 16 }, { wch: 16 }, { wch: 16 },
            { wch: 12 }, { wch: 10 }, { wch: 18 }
        ]
        const wb = XLSX.utils.book_new()
        XLSX.utils.book_append_sheet(wb, ws, '队伍数据')
        XLSX.writeFile(wb, `player_team_export_${new Date().toISOString().slice(0, 10)}.xlsx`)

        const cost = resp.data.query_ms != null ? `，查询耗时 ${resp.data.query_ms}ms` : ''
        const hit = resp.data.cache_hit ? '，命中缓存' : ''
        nmessage.success(`已导出 ${allList.length} 条队伍数据${cost}${hit}`)
    } catch (e) {
        nmessage.error('导出失败: ' + e)
    } finally {
        exporting.value = false
    }
}

const resolveHeroId = (id: number | string) => {
    if (!id) return id
    const num = Number(id)
    return num >= 130000 ? num - 30000 : num
}

const getHeroName = (id: number) => {
    if (!id) return ''
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.name : `ID:${id}`
}

const getHeroType = (id: number) => {
    if (!id) return ''
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.type : ''
}

const getHeroIcon = (id: number) => {
    if (!id) return id
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.iconId : id
}

const getSkillName = (id: number | string) => {
    if (!id) return ''
    const skill = skillMap[String(id)]
    return skill ? skill.name : ''
}

const getSkillQuality = (id: number | string) => {
    if (!id) return ''
    const skill = skillMap[String(id)]
    return skill ? skill.zfQuality : ''
}

const parseGearInfo = (gearStr: string, role = 'attack') => {
    if (!gearStr) return [null, null, null]
    const rawSlots = gearStr.split(';').map(s => s.trim()).filter(Boolean)
    const slots = rawSlots.length >= 4
        ? (role === 'attack' ? rawSlots.slice(1, 4) : rawSlots.slice(0, 3))
        : rawSlots.slice(0, 3)
    const result: any[] = []
    for (let i = 0; i < slots.length; i++) {
        const parts = slots[i].split(',')
        if (parts.length !== 3) {
            result.push(null)
            continue
        }
        const gearId = parseInt(parts[0])
        const level = parseInt(parts[1])
        const refine = parseInt(parts[2])
        if (gearId === 0) {
            result.push(null)
        } else {
            const gear = gearMap[gearId]
            result.push({ id: gearId, name: gear ? gear.name : `ID:${gearId}`, level, refine })
        }
    }
    while (result.length < 3) result.push(null)
    return result
}

const getGearDisplay = (gearStr: string, index: number, role = 'attack') => {
    const gears = parseGearInfo(gearStr, role)
    const g: any = gears[index]
    if (!g) return ''
    return `${g.name} Lv.${g.level}`
}

const parseSkillInfo = (str: string, role: string) => {
    if (!str) return []
    let groups = String(str).split(';').filter(s => s.trim() !== '')
    let parsed = groups.map(g => {
        const parts = g.split(',')
        return {
            heroIndex: parseInt(parts[0]),
            skills: [
                { id: parts[1], level: parseInt(parts[2]) },
                { id: parts[3], level: parseInt(parts[4]) },
                { id: parts[5], level: parseInt(parts[6]) }
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

const fillSkillRows = (allSkillInfo: string, role: string) => {
    const next = emptySkillRows()
    const parsed = parseSkillInfo(allSkillInfo, role)
    for (let i = 0; i < 3; i++) {
        const skills = parsed[i]?.skills || []
        next[i] = {
            main: Number(skills[0]?.id || 0),
            main_level: Number(skills[0]?.level || 10),
            skill1: Number(skills[1]?.id || 0),
            skill1_level: Number(skills[1]?.level || 10),
            skill2: Number(skills[2]?.id || 0),
            skill2_level: Number(skills[2]?.level || 10)
        }
    }
    skillRows.value = next
}

const buildSkillInfo = () => {
    const groups = skillRows.value.map((row, index) => {
        const heroIndex = teamForm.value.role === 'defend' ? 6 - index : index + 1
        return [
            heroIndex,
            Number(row.main || 0), Number(row.main_level || 0),
            Number(row.skill1 || 0), Number(row.skill1_level || 0),
            Number(row.skill2 || 0), Number(row.skill2_level || 0)
        ].join(',')
    })
    return groups.join(';')
}

const formatTime = (ts: number) => {
    if (!ts) return ''
    const d = new Date(ts * 1000)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const getPlayerTeams = (): Record<string, any[]> => {
    const map: Record<string, any[]> = {}
    results.value.forEach(r => {
        if (!map[r.player_name]) map[r.player_name] = []
        map[r.player_name].push(r)
    })
    return map
}

const roleLabel = (role: string) => role === 'attack' ? '攻' : '守'
const roleType = (role: string) => role === 'attack' ? 'error' : 'info'
const sourceLabel = (team: any) => team.manual ? '手工' : '战报'
const sourceType = (team: any) => team.manual ? 'warning' : 'success'
const sourceKey = (team: any) => `${team.source_type || 'battle_report'}-${team.source_id || team.battle_id}-${team.role}`

const qualityColor = (q: string) => {
    if (q === 'S') return 'var(--color-warning)'
    if (q === 'A') return 'var(--color-info)'
    if (q === 'B') return 'var(--color-success)'
    return 'var(--color-text-muted)'
}

const openCreateTeam = () => {
    formMode.value = 'create'
    teamForm.value = emptyTeamForm()
    skillRows.value = emptySkillRows()
    teamModalVisible.value = true
}

const openEditTeam = (team: any) => {
    formMode.value = 'edit'
    teamForm.value = {
        id: team.manual ? Number(team.source_id || 0) : 0,
        player_name: team.player_name || '',
        union_name: team.union_name || '',
        idu: team.idu || '',
        role: team.role || 'attack',
        time: Number(team.time || Math.floor(Date.now() / 1000)),
        battle_id: Number(team.battle_id || 0),
        hero1_id: Number(team.hero1_id || 0),
        hero2_id: Number(team.hero2_id || 0),
        hero3_id: Number(team.hero3_id || 0),
        hero1_level: Number(team.hero1_level || 50),
        hero2_level: Number(team.hero2_level || 50),
        hero3_level: Number(team.hero3_level || 50),
        hero1_star: Number(team.hero1_star || 0),
        hero2_star: Number(team.hero2_star || 0),
        hero3_star: Number(team.hero3_star || 0),
        total_star: Number(team.total_star || 0),
        hp: Number(team.hp || 30000),
        all_skill_info: team.all_skill_info || '',
        gear: team.gear || '',
        hero_type: team.hero_type || '',
        note: team.note || '',
        source_battle_id: team.manual ? 0 : Number(team.source_id || team.battle_id || 0),
        source_role: team.manual ? '' : team.role
    }
    fillSkillRows(teamForm.value.all_skill_info, teamForm.value.role)
    teamModalVisible.value = true
}

const saveTeam = async () => {
    if (!teamForm.value.player_name) {
        nmessage.warning('请填写玩家名称')
        return
    }
    if (!teamForm.value.hero1_id || !teamForm.value.hero2_id || !teamForm.value.hero3_id) {
        nmessage.warning('请填写三名武将 ID')
        return
    }

    savingTeam.value = true
    try {
        teamForm.value.total_star = totalStarAuto.value
        teamForm.value.all_skill_info = buildSkillInfo()
        const payload = JSON.stringify(teamForm.value)
        const res = teamForm.value.id
            ? await UpdateManualPlayerTeam(Number(teamForm.value.id), payload)
            : await CreateManualPlayerTeam(payload)
        const resp = JSON.parse(res)
        if (resp.code === 200) {
            nmessage.success(resp.msg || '已保存')
            teamModalVisible.value = false
            doSearch(page.value)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('保存失败: ' + e)
    } finally {
        savingTeam.value = false
    }
}

const hideTeam = async (team: any) => {
    try {
        const res = await HidePlayerTeam(team.source_type || 'battle_report', Number(team.source_id || team.battle_id), team.role)
        const resp = JSON.parse(res)
        if (resp.code === 200) {
            nmessage.success(resp.msg || '已隐藏')
            doSearch(page.value)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('隐藏失败: ' + e)
    }
}

const deleteManualTeam = async (team: any) => {
    try {
        const res = await DeleteManualPlayerTeam(Number(team.source_id))
        const resp = JSON.parse(res)
        if (resp.code === 200) {
            nmessage.success(resp.msg || '已删除')
            doSearch(page.value)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('删除失败: ' + e)
    }
}

const openHiddenManager = async () => {
    hiddenModalVisible.value = true
    await loadHiddenTeams()
}

const loadHiddenTeams = async () => {
    hiddenLoading.value = true
    try {
        const res = await GetHiddenPlayerTeams()
        const resp = JSON.parse(res)
        if (resp.code === 200) hiddenTeams.value = resp.data || []
        else nmessage.error(resp.msg)
    } catch (e) {
        nmessage.error('读取隐藏队伍失败: ' + e)
    } finally {
        hiddenLoading.value = false
    }
}

const restoreHiddenTeam = async (row: any) => {
    try {
        const res = await RestoreHiddenPlayerTeam(row.source_type, Number(row.source_id), row.role)
        const resp = JSON.parse(res)
        if (resp.code === 200) {
            nmessage.success(resp.msg || '已恢复')
            await loadHiddenTeams()
            doSearch(page.value)
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('恢复失败: ' + e)
    }
}
</script>

<template>
    <div class="team-query">
        <div class="query-header">
            <h2 class="query-title">
                <Swords :size="20" />
                队伍查询
            </h2>
            <p class="query-desc">查询玩家队伍配置与战法，默认替换同玩家共享 2 个武将 ID 的旧队伍；手工修正不会改原始战报</p>
        </div>

        <div class="search-box">
            <n-input v-model:value="searchName" placeholder="玩家名称" clearable @keyup.enter="doSearch()" />
            <n-input v-model:value="searchUnion" placeholder="同盟" clearable @keyup.enter="doSearch()" />
            <n-input v-model:value="searchIdu" placeholder="队伍ID" clearable @keyup.enter="doSearch()" />
            <n-button type="primary" @click="doSearch()" :loading="loading">
                <template #icon><Search :size="16" /></template>
                查询
            </n-button>
            <n-button @click="openCreateTeam()">
                <template #icon><Plus :size="16" /></template>
                新增队伍
            </n-button>
            <n-button @click="openHiddenManager()">
                <template #icon><Settings :size="16" /></template>
                隐藏管理
            </n-button>
            <n-button @click="doExport()" :loading="exporting">
                <template #icon><Download :size="16" /></template>
                导出Excel
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
                <span>{{ Object.keys(getPlayerTeams()).length }} 位玩家</span>
                <span>{{ results.length }} 支队伍</span>
                <span>共 {{ total }} 条</span>
                <span v-if="queryMs !== null">耗时 {{ queryMs }}ms</span>
                <span v-if="cacheHit">命中缓存</span>
                <span>已合并手工修正</span>
            </div>

            <div v-if="viewMode === 'compact'" class="compact-view">
                <table class="team-table">
                    <thead>
                        <tr>
                            <th>玩家</th>
                            <th>队伍 (大营→中军→前锋)</th>
                            <th>宝物</th>
                            <th>红度</th>
                            <th>角色</th>
                            <th>来源</th>
                            <th>时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="team in results" :key="sourceKey(team)">
                            <td class="player-cell">
                                <span class="player-name">{{ team.player_name }}</span>
                                <span class="player-idu">ID:{{ team.idu }}</span>
                            </td>
                            <td class="team-cell">
                                <template v-for="i in 3" :key="i">
                                    <div class="hero-mini">
                                        <img v-if="team[`hero${i}_id`]" :src="`https://g0.gph.netease.com/ngsocial/community/stzb/cn/cards/cut/card_small_${getHeroIcon(team[`hero${i}_id`])}.jpg?gameid=g10`" @error="($event.target as any).style.display='none'" />
                                        <span class="hero-mini-name">{{ getHeroName(team[`hero${i}_id`]) }}<span class="hero-mini-type">{{ getHeroType(team[`hero${i}_id`]) }}</span></span>
                                    </div>
                                    <span v-if="i < 3" class="team-arrow">→</span>
                                </template>
                            </td>
                            <td class="gear-cell">
                                <div v-for="(g, gi) in parseGearInfo(team.gear, team.role)" :key="gi" class="gear-item">
                                    <span v-if="g" class="gear-name">{{ g.name }} <span class="gear-level">Lv.{{ g.level }}</span></span>
                                    <span v-else class="gear-empty">-</span>
                                </div>
                            </td>
                            <td class="star-cell"><span class="star-value">{{ team.total_star }}</span></td>
                            <td class="role-cell">
                                <n-tag :type="roleType(team.role)" size="small" :bordered="false">{{ roleLabel(team.role) }}</n-tag>
                            </td>
                            <td>
                                <n-tag :type="sourceType(team)" size="small" :bordered="false">{{ sourceLabel(team) }}</n-tag>
                            </td>
                            <td class="time-cell">{{ formatTime(team.time) }}</td>
                            <td class="action-cell">
                                <n-button quaternary size="tiny" @click="openEditTeam(team)">
                                    <template #icon><Pencil :size="14" /></template>
                                </n-button>
                                <n-popconfirm @positive-click="hideTeam(team)">
                                    <template #trigger>
                                        <n-button quaternary size="tiny">
                                            <template #icon><EyeOff :size="14" /></template>
                                        </n-button>
                                    </template>
                                    隐藏这支队伍？
                                </n-popconfirm>
                                <n-popconfirm v-if="team.manual" @positive-click="deleteManualTeam(team)">
                                    <template #trigger>
                                        <n-button quaternary size="tiny" type="error">
                                            <template #icon><Trash2 :size="14" /></template>
                                        </n-button>
                                    </template>
                                    永久删除这条手工队伍？
                                </n-popconfirm>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div v-else class="list-view">
                <div class="player-group" v-for="(teams, playerName) in getPlayerTeams()" :key="playerName">
                    <div class="player-header">
                        <span class="player-title">{{ playerName }}</span>
                        <span class="player-count">{{ teams.length }} 支队伍</span>
                    </div>
                    <div class="team-list">
                        <div class="team-item" v-for="team in teams" :key="sourceKey(team)">
                            <div class="team-meta">
                                <n-tag :type="roleType(team.role)" size="tiny" :bordered="false">{{ roleLabel(team.role) }}</n-tag>
                                <n-tag :type="sourceType(team)" size="tiny" :bordered="false">{{ sourceLabel(team) }}</n-tag>
                                <span class="team-idu">ID {{ team.idu }}</span>
                                <span class="team-star"><Star :size="12" /> {{ team.total_star }}红</span>
                                <span class="team-time">{{ formatTime(team.time) }}</span>
                                <div class="team-actions">
                                    <n-button quaternary size="tiny" @click="openEditTeam(team)">
                                        <template #icon><Pencil :size="14" /></template>
                                        编辑
                                    </n-button>
                                    <n-popconfirm @positive-click="hideTeam(team)">
                                        <template #trigger>
                                            <n-button quaternary size="tiny">
                                                <template #icon><EyeOff :size="14" /></template>
                                                隐藏
                                            </n-button>
                                        </template>
                                        隐藏这支队伍？
                                    </n-popconfirm>
                                    <n-popconfirm v-if="team.manual" @positive-click="deleteManualTeam(team)">
                                        <template #trigger>
                                            <n-button quaternary size="tiny" type="error">
                                                <template #icon><Trash2 :size="14" /></template>
                                                删除
                                            </n-button>
                                        </template>
                                        永久删除这条手工队伍？
                                    </n-popconfirm>
                                </div>
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
                                        <span v-for="(skill, si) in (parseSkillInfo(team.all_skill_info, team.role)[i-1]?.skills || [])" :key="si" class="skill-tag" :style="{ borderColor: qualityColor(getSkillQuality(skill.id)) }">
                                            {{ getSkillName(skill.id) || `ID:${skill.id}` }}
                                        </span>
                                    </div>
                                    <div v-if="getGearDisplay(team.gear, i-1, team.role)" class="hero-gear">
                                        <span class="gear-tag">{{ getGearDisplay(team.gear, i-1, team.role) }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <n-modal v-model:show="teamModalVisible" preset="card" :title="formMode === 'create' ? '新增队伍' : '编辑队伍'" class="team-edit-modal">
            <n-form label-placement="top">
                <n-grid :cols="3" :x-gap="12">
                    <n-gi><n-form-item label="玩家"><n-input v-model:value="teamForm.player_name" /></n-form-item></n-gi>
                    <n-gi><n-form-item label="同盟"><n-input v-model:value="teamForm.union_name" /></n-form-item></n-gi>
                    <n-gi><n-form-item label="队伍ID"><n-input v-model:value="teamForm.idu" /></n-form-item></n-gi>
                    <n-gi><n-form-item label="记录类型"><n-select v-model:value="teamForm.role" :options="roleOptions" @update:value="fillSkillRows(teamForm.all_skill_info, teamForm.role)" /></n-form-item></n-gi>
                    <n-gi><n-form-item label="记录时间"><n-input-number v-model:value="teamForm.time" :show-button="false" /></n-form-item></n-gi>
                    <n-gi><n-form-item label="兵力"><n-input-number v-model:value="teamForm.hp" :show-button="false" /></n-form-item></n-gi>
                </n-grid>

                <n-divider>武将</n-divider>
                <n-grid :cols="3" :x-gap="12">
                    <n-gi v-for="i in 3" :key="i">
                        <div class="form-hero-block">
                            <div class="form-hero-title">{{ ['大营', '中军', '前锋'][i - 1] }}</div>
                            <n-form-item label="武将ID"><n-input-number v-model:value="teamForm[`hero${i}_id`]" :show-button="false" /></n-form-item>
                            <n-form-item label="等级"><n-input-number v-model:value="teamForm[`hero${i}_level`]" :show-button="false" /></n-form-item>
                            <n-form-item label="红度"><n-input-number v-model:value="teamForm[`hero${i}_star`]" :show-button="false" /></n-form-item>
                            <div class="form-hero-name">{{ getHeroName(teamForm[`hero${i}_id`]) }}</div>
                        </div>
                    </n-gi>
                </n-grid>

                <n-divider>战法</n-divider>
                <div class="skill-editor">
                    <div class="skill-row" v-for="(row, index) in skillRows" :key="index">
                        <span class="skill-row-title">{{ ['大营', '中军', '前锋'][index] }}</span>
                        <n-input-number v-model:value="row.main" placeholder="主战法ID" :show-button="false" />
                        <n-input-number v-model:value="row.main_level" placeholder="等级" :show-button="false" />
                        <n-input-number v-model:value="row.skill1" placeholder="战法1 ID" :show-button="false" />
                        <n-input-number v-model:value="row.skill1_level" placeholder="等级" :show-button="false" />
                        <n-input-number v-model:value="row.skill2" placeholder="战法2 ID" :show-button="false" />
                        <n-input-number v-model:value="row.skill2_level" placeholder="等级" :show-button="false" />
                    </div>
                </div>

                <n-grid :cols="2" :x-gap="12" class="raw-fields">
                    <n-gi><n-form-item label="宝物原始值"><n-input v-model:value="teamForm.gear" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></n-form-item></n-gi>
                    <n-gi><n-form-item label="兵种原始值"><n-input v-model:value="teamForm.hero_type" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></n-form-item></n-gi>
                    <n-gi :span="2"><n-form-item label="备注"><n-input v-model:value="teamForm.note" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></n-form-item></n-gi>
                </n-grid>
            </n-form>

            <template #footer>
                <n-space justify="end">
                    <n-button @click="teamModalVisible = false">取消</n-button>
                    <n-button type="primary" :loading="savingTeam" @click="saveTeam">保存</n-button>
                </n-space>
            </template>
        </n-modal>

        <n-modal v-model:show="hiddenModalVisible" preset="card" title="隐藏队伍管理" class="hidden-modal">
            <div v-if="hiddenLoading" class="loading small">
                <n-spin size="small" />
                <span>读取中...</span>
            </div>
            <n-empty v-else-if="hiddenTeams.length === 0" description="暂无隐藏队伍" />
            <div v-else class="hidden-list">
                <div class="hidden-row" v-for="row in hiddenTeams" :key="`${row.source_type}-${row.source_id}-${row.role}`">
                    <div>
                        <n-tag size="small" :bordered="false">{{ row.source_type === 'manual' ? '手工' : '战报' }}</n-tag>
                        <span>{{ row.player_name || '-' }}</span>
                        <span>ID {{ row.idu || row.source_id }}</span>
                        <span>{{ roleLabel(row.role) }}</span>
                    </div>
                    <n-button size="small" @click="restoreHiddenTeam(row)">
                        <template #icon><RotateCcw :size="14" /></template>
                        恢复
                    </n-button>
                </div>
            </div>
        </n-modal>
    </div>
</template>

<style scoped lang="scss">
.team-query {
    max-width: 1180px;
    margin: 0 auto;
    color: var(--color-text);
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
        color: var(--color-text-secondary);
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
    color: var(--color-text-secondary);

    &.small {
        padding: 24px 0;
    }
}

.results .result-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    padding: 12px 16px;
    background: rgba(255, 248, 232, 0.06);
    border-radius: 8px;
    margin-bottom: 16px;
    font-size: 13px;
    color: var(--color-text-secondary);
}

.compact-view {
    overflow-x: auto;

    .team-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;

        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--color-border-light);
            vertical-align: middle;
        }

        th {
            background: rgba(214, 164, 71, 0.1);
            font-weight: 500;
            color: var(--color-text-secondary);
        }

        tr:hover td {
            background: var(--color-surface-hover);
        }
    }
}

.player-cell {
    .player-name {
        font-weight: 500;
        color: var(--color-text);
    }
    .player-idu {
        display: block;
        font-size: 11px;
        color: var(--color-text-secondary);
    }
}

.team-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 280px;
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
        white-space: nowrap;
    }

    .hero-mini-type {
        margin-left: 2px;
        font-size: 11px;
    }
}

.team-arrow {
    color: var(--color-text-muted);
    font-size: 10px;
}

.star-cell .star-value {
    font-weight: 600;
    color: var(--color-accent);
}

.gear-cell {
    font-size: 11px;
    min-width: 110px;

    .gear-item {
        margin-bottom: 2px;
    }

    .gear-name {
        color: var(--color-info);
    }

    .gear-level {
        color: var(--color-text-secondary);
        font-size: 10px;
    }

    .gear-empty {
        color: var(--color-text-muted);
    }
}

.time-cell {
    color: var(--color-text-secondary);
    font-size: 12px;
    white-space: nowrap;
}

.action-cell {
    display: flex;
    gap: 2px;
    white-space: nowrap;
}

.list-view {
    .player-group {
        margin-bottom: 20px;
        background: var(--color-surface);
        border-radius: 10px;
        border: 1px solid var(--color-border);
        overflow: hidden;
    }

    .player-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background: rgba(214, 164, 71, 0.08);
        border-bottom: 1px solid var(--color-border-light);
    }

    .player-title {
        font-weight: 600;
        color: var(--color-text);
    }

    .player-count {
        font-size: 12px;
        color: var(--color-text-secondary);
    }

    .team-list {
        padding: 12px;
    }

    .team-item {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
        background: rgba(255, 248, 232, 0.04);

        &:last-child {
            margin-bottom: 0;
        }
    }

    .team-meta {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        flex-wrap: wrap;

        .team-idu {
            font-size: 12px;
            color: var(--color-text-secondary);
        }

        .team-star {
            display: flex;
            align-items: center;
            gap: 2px;
            font-size: 12px;
            color: var(--color-accent);
        }

        .team-time {
            font-size: 12px;
            color: var(--color-text-secondary);
            margin-left: auto;
        }

        .team-actions {
            display: flex;
            align-items: center;
            gap: 4px;
        }
    }

    .team-heroes {
        display: flex;
        gap: 12px;
    }

    .hero-card {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 10px;
        background: rgba(255, 248, 232, 0.05);
        border-radius: 6px;
        border: 1px solid var(--color-border-light);
        flex: 1;
        min-width: 0;

        .hero-main {
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
        }

        img {
            width: 32px;
            height: 32px;
            border-radius: 4px;
            flex-shrink: 0;
        }

        .hero-name {
            font-size: 13px;
            font-weight: 500;
            white-space: nowrap;
        }

        .hero-type, .hero-level {
            font-size: 11px;
            color: var(--color-text-secondary);
            white-space: nowrap;
        }

        .hero-skills {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .skill-tag {
            padding: 2px 8px;
            font-size: 11px;
            background: rgba(255, 248, 232, 0.04);
            border: 1px solid;
            border-radius: 4px;
            color: var(--color-text-secondary);
            white-space: nowrap;
        }

        .gear-tag {
            display: inline-block;
            padding: 2px 8px;
            font-size: 11px;
            background: rgba(106, 164, 184, 0.12);
            border: 1px solid var(--color-info);
            border-radius: 4px;
            color: var(--color-info);
            white-space: nowrap;
        }
    }
}

.team-edit-modal {
    width: min(980px, 92vw);
}

.form-hero-block {
    padding: 10px;
    border: 1px solid var(--color-border-light);
    border-radius: 8px;
    background: rgba(255, 248, 232, 0.04);

    .form-hero-title {
        font-weight: 600;
        margin-bottom: 8px;
        color: var(--color-accent);
    }

    .form-hero-name {
        min-height: 20px;
        font-size: 12px;
        color: var(--color-text-secondary);
    }
}

.skill-editor {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;

    .skill-row {
        display: grid;
        grid-template-columns: 56px repeat(6, minmax(84px, 1fr));
        gap: 8px;
        align-items: center;
    }

    .skill-row-title {
        font-size: 13px;
        color: var(--color-text-secondary);
    }
}

.raw-fields {
    margin-top: 12px;
}

.hidden-modal {
    width: min(720px, 90vw);
}

.hidden-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.hidden-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid var(--color-border-light);
    border-radius: 8px;
    background: rgba(255, 248, 232, 0.04);

    > div {
        display: flex;
        align-items: center;
        gap: 10px;
        color: var(--color-text-secondary);
        font-size: 13px;
    }
}

@media (max-width: 900px) {
    .list-view .team-heroes {
        flex-direction: column;
    }

    .skill-editor .skill-row {
        grid-template-columns: 1fr 1fr;

        .skill-row-title {
            grid-column: 1 / -1;
        }
    }
}
</style>
