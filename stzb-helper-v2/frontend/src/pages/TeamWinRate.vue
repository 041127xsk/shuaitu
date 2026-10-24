<script setup lang="ts">
import { ref, computed, h, watch, onMounted, onUnmounted } from 'vue'
import { NCard, NButton, NInput, NInputNumber, NEmpty, NSpin, NTag, NPagination, NDataTable, NModal, useMessage } from 'naive-ui'
import { GetMaterializedStatsStatus, GetPlayerTeamRelatedBattles, GetTeamWinRate, GetTeamWinRateByTeam, RebuildMaterializedStats } from '../../wailsjs/go/main/App'
import { Search, Image, Users, RefreshCw, ScrollText } from 'lucide-vue-next'
import { herocfg, skillcfg } from '../cfg'

const heroMap = JSON.parse(herocfg)
const skillMap = JSON.parse(skillcfg)

const nmessage = useMessage()
const loading = ref(false)
const results = ref([])

const searchName = ref('')
const searchUnion = ref('')
const searchIdu = ref('')
const minLevel = ref(30)
const minHp = ref(20000)

const hasSearched = ref(false)
const useImageMode = ref(true)
const groupByPlayer = ref(true)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const queryMs = ref<number | null>(null)
const cacheHit = ref(false)
const source = ref('')
const statsReady = ref(false)
const rebuilding = ref(false)
const rebuildProgressText = ref('')
let statsPollTimer: number | undefined

// 战报弹窗：和队伍查询一样按需展开原始战报，不额外占列宽。
const battleModalVisible = ref(false)
const battleModalTitle = ref('')
const battleLoading = ref(false)
const battleList = ref<any[]>([])
const battleTotal = ref(0)
const battleRow = ref<any>(null)
// 逐条战报的展开状态：默认全部收起，点一下展开该场的逐武将战损明细。
const expandedBattles = ref<Record<number, boolean>>({})

const toggleBattleExpand = (battleId) => {
    expandedBattles.value = { ...expandedBattles.value, [battleId]: !expandedBattles.value[battleId] }
}

const battleKey = (row) => {
    // 按玩家口径：玩家 + 角色 + idu + 阵容；按队伍口径：只有阵容。
    if (groupByPlayer.value) {
        return `${row.player_name || ''}|${row.role || ''}|${row.idu || ''}|${row.hero1_id}_${row.hero2_id}_${row.hero3_id}`
    }
    return `__team__|${row.hero1_id}_${row.hero2_id}_${row.hero3_id}`
}

const resultType = (label) => {
    if (label === '胜') return 'success'
    if (label === '负') return 'error'
    if (label === '平') return 'warning'
    return 'default'
}

const roleLabel = (role) => (role === 'defend' ? '守方' : '攻方')

// 兵力数字千分位，0 显示为 0（战损为 0 是有意义的信息，不能显示成 —）
const fmtHp = (v) => Number(v || 0).toLocaleString()

const openRelatedBattles = async (row) => {
    battleRow.value = row
    battleModalTitle.value = groupByPlayer.value
        ? `${row.player_name || ''} · ${row.team_names || ''}`
        : (row.team_names || '')
    battleModalVisible.value = true
    battleLoading.value = true
    battleList.value = []
    battleTotal.value = 0
    expandedBattles.value = {}
    try {
        // 按队伍组合时没有单一玩家，只按阵容查（跨玩家）；按玩家时带上玩家 + 角色。
        const playerName = groupByPlayer.value ? (row.player_name || '') : ''
        const role = groupByPlayer.value ? (row.role || '') : ''
        const idu = groupByPlayer.value ? (row.idu || '') : ''
        const resp = JSON.parse(await GetPlayerTeamRelatedBattles(
            playerName, role, idu,
            row.hero1_id, row.hero2_id, row.hero3_id, 1, 100,
        ))
        if (resp.code === 200) {
            battleList.value = resp.data.list || []
            battleTotal.value = resp.data.total || 0
            // 默认展开第一条，让「详细战损」一打开就能看到；其余点一下即可展开
            if (battleList.value.length > 0) {
                expandedBattles.value = { [battleList.value[0].battle_id]: true }
            }
        } else {
            nmessage.error(resp.msg)
        }
    } catch (e) {
        nmessage.error('战报加载失败: ' + e)
    } finally {
        battleLoading.value = false
    }
}

const doSearch = (newPage?: number) => {
    if (typeof newPage === 'number') page.value = newPage
    else page.value = 1
    loading.value = true
    results.value = []
    hasSearched.value = true
    const apiFn = groupByPlayer.value ? GetTeamWinRate : GetTeamWinRateByTeam
    apiFn(searchName.value, searchUnion.value, searchIdu.value, page.value, pageSize.value, minLevel.value, minHp.value).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            results.value = (resp.data.list || []).map(prepareWinRateDisplay)
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
        statsReady.value = !!resp.data.winrate_ready
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

const resolveHeroId = (id) => {
    if (!id) return id
    const num = Number(id)
    return num >= 130000 ? num - 30000 : num
}

const getHeroIconId = (id) => {
    if (!id) return id
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.iconId : id
}

const getHeroName = (id) => {
    if (!id) return ''
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.name : `未知(${id})`
}

const getHeroCountry = (id) => {
    if (!id) return ''
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.country : ''
}

const getHeroType = (id) => {
    if (!id) return ''
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.type : ''
}

const getHeroQuality = (id) => {
    if (!id) return 5
    const hero = heroMap[String(resolveHeroId(id))]
    return hero ? hero.quality : 5
}

const getSkillName = (id) => {
    if (!id) return ''
    const skill = skillMap[String(id)]
    return skill ? skill.name : `未知(${id})`
}

const getSkillQuality = (id) => {
    if (!id) return ''
    const skill = skillMap[String(id)]
    return skill ? skill.zfQuality : ''
}

const getSkillType = (id) => {
    if (!id) return ''
    const skill = skillMap[String(id)]
    return skill ? skill.type : ''
}

const prepareWinRateDisplay = (team) => {
    const parsedSkillInfo = parseSkillInfo(team.all_skill_info, team.role)
    const enrichedSkillInfo = parsedSkillInfo.map(group => ({
        ...group,
        skills: group.skills.map(skill => ({
            ...skill,
            name: getSkillName(skill.id),
            quality: getSkillQuality(skill.id),
            type: getSkillType(skill.id),
        })),
    }))
    const heroes = [1, 2, 3].map(i => {
        const id = team[`hero${i}_id`]
        const star = Number(team[`hero${i}_star`] || 0)
        const quality = getHeroQuality(id)
        return {
            id,
            name: getHeroName(id),
            country: getHeroCountry(id),
            type: getHeroType(id),
            iconId: getHeroIconId(id),
            imageUrl: id ? `https://cbg-stzb.res.netease.com/game_res/cards/cut/card_medium_${getHeroIconId(id)}.jpg` : '',
            star,
            emptyStar: Math.max(0, quality - star),
            skills: enrichedSkillInfo[i - 1]?.skills || [],
        }
    })
    const totalBattles = Number(team.total_battles || 0)
    const lossRate = totalBattles > 0 ? Math.round(Number(team.loss_count || 0) / totalBattles * 1000) / 10 : 0
    const drawRate = totalBattles > 0 ? Math.round(Number(team.draw_count || 0) / totalBattles * 1000) / 10 : 0
    return {
        ...team,
        heroes,
        parsed_skill_info: enrichedSkillInfo,
        hero_names: heroes.map(hero => `${hero.name}${hero.type ? `(${hero.type})` : ''}`).join(' / '),
        team_names: heroes.map(hero => hero.name).join(' / '),
        formatted_time: formatTime(team.last_time),
        loss_rate: lossRate,
        draw_rate: drawRate,
    }
}

const parseSkillInfo = (str, role) => {
    if (!str) return []
    const groups = String(str).split(';').filter(s => s.trim() !== '')
    const parsed = groups.map(g => {
        const parts = g.split(',')
        return {
            index: parseInt(parts[0]),
            skills: [
                { id: parts[1], level: parseInt(parts[2]) },
                { id: parts[3], level: parseInt(parts[4]) },
                { id: parts[5], level: parseInt(parts[6]) },
            ]
        }
    })
    let filtered = role === 'defend'
        ? parsed.filter(g => g.index >= 4 && g.index <= 6)
        : parsed.filter(g => g.index >= 1 && g.index <= 3)
    if (role === 'defend') filtered.reverse()
    return filtered
}

const formatTime = (ts) => {
    if (!ts) return ''
    const d = new Date(ts * 1000)
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const winRateColor = (rate) => {
    if (rate >= 70) return '#22c55e'
    if (rate >= 50) return '#3b82f6'
    if (rate >= 30) return '#f59e0b'
    return '#ef4444'
}

const lossRateColor = (rate) => {
    if (rate >= 70) return '#ef4444'
    if (rate >= 50) return '#f59e0b'
    if (rate >= 30) return '#3b82f6'
    return '#22c55e'
}

const groupedResults = computed(() => {
    const map = {}
    results.value.forEach(r => {
        if (!map[r.player_name]) map[r.player_name] = []
        map[r.player_name].push(r)
    })
    return map
})

const tableData = computed(() => results.value)

watch(groupByPlayer, () => {
    page.value = 1
    results.value = []
    if (hasSearched.value) doSearch()
})

onMounted(async () => {
    await refreshStatsStatus()
    if (rebuilding.value) startStatsPolling()
})
onUnmounted(stopStatsPolling)

const playerColumns: any[] = [
    {
        title: '玩家',
        key: 'player_name',
        width: 120,
        ellipsis: { tooltip: true },
    },
    {
        title: '队伍',
        key: 'heroes',
        minWidth: 200,
        render(row) {
            return row.hero_names
        }
    },
    {
        title: '战法',
        key: 'skills',
        width: 200,
        render(row) {
            const lines = (row.parsed_skill_info || []).map(g => {
                const names = g.skills.slice(1).filter(s => s.id && s.id !== '0').map(s => s.name || getSkillName(s.id))
                return names.join('/')
            }).filter(Boolean)
            return h('div', { style: { whiteSpace: 'pre-line' } }, lines.join('\n'))
        }
    },
    {
        title: '红度',
        key: 'total_star',
        width: 60,
        align: 'center',
        sorter: (a, b) => a.total_star - b.total_star,
    },
    {
        title: '总场次',
        key: 'total_battles',
        width: 80,
        align: 'center',
        sorter: (a, b) => a.total_battles - b.total_battles,
    },
    {
        title: '胜',
        key: 'win_count',
        width: 60,
        align: 'center',
        sorter: (a, b) => a.win_count - b.win_count,
    },
    {
        title: '负',
        key: 'loss_count',
        width: 60,
        align: 'center',
        sorter: (a, b) => a.loss_count - b.loss_count,
    },
    {
        title: '平',
        key: 'draw_count',
        width: 60,
        align: 'center',
        sorter: (a, b) => a.draw_count - b.draw_count,
    },
    {
        title: '胜率',
        key: 'win_rate',
        width: 80,
        align: 'center',
        sorter: (a, b) => a.win_rate - b.win_rate,
        defaultSortOrder: 'descend',
        render(row) {
            const rate = row.win_rate || 0
            return h('span', { style: { color: winRateColor(rate), fontWeight: '700' } }, rate + '%')
        }
    },
    {
        // 战损比 = 对方累计战损 / 我方累计战损，> 1 表示我方赚。
        // 战损 = 伤兵 + 死兵：这一场被打掉多少兵就算多少损失，伤兵战后恢复也算本场损耗。
        // 按玩家口径：该玩家所有队伍的战损累加后再相除。
        // 只统计双方兵力都 > 20000 的场次（完美克制时一方可能只带几十兵，
        // 比值会被极端放大到几百倍）。
        title: '战损比',
        key: 'loss_ratio',
        width: 90,
        align: 'center',
        sorter: (a, b) => (a.loss_ratio || 0) - (b.loss_ratio || 0),
        render(row) {
            const ratio = row.loss_ratio || 0
            if (!ratio) {
                return h('span', { style: { color: '#bbb' } }, '—')
            }
            const color = ratio >= 1 ? '#18a058' : '#d03050'
            return h('span', {
                style: { color, fontWeight: '700' },
                title: `战损(伤+死) 我方 ${fmtHp(row.our_lost_hp)} / 对方 ${fmtHp(row.enemy_lost_hp)}；`
                    + `其中死兵 我方 ${fmtHp(row.our_killed_hp)} / 对方 ${fmtHp(row.enemy_killed_hp)}；`
                    + `统计场次 ${row.loss_ratio_battles || 0}（双方兵力均 > 20000）`,
            }, ratio.toFixed(2))
        }
    },
    {
        // 损耗率 = 我方累计战损（伤+死）/ 我方累计开战兵力（历史累计，与战损比同一批场次）。
        // 因为分子必然 <= 分母，累计损耗率一定 <= 100%；渲染时再做一次钳制兜底。
        // 注意：字段名必须是 destroyed_rate，不能叫 loss_rate ——
        // loss_rate 已被「负率」(loss_count/total_battles) 占用，两者撞名会导致
        // 损耗率列显示成负率的数值（例如负率 3.52% 被当成损耗率 352%）。
        title: '损耗率',
        key: 'destroyed_rate',
        width: 90,
        align: 'center',
        sorter: (a, b) => (a.destroyed_rate || 0) - (b.destroyed_rate || 0),
        render(row) {
            const rate = Number(row.destroyed_rate || 0)
            if (!rate) {
                return h('span', { style: { color: '#bbb' } }, '—')
            }
            // 兜底钳制：比值口径上不会超过 1，真出现异常也不显示 >100%
            const pct = Math.min(rate, 1) * 100
            const color = pct >= 60 ? '#d03050' : pct >= 30 ? '#f59e0b' : '#18a058'
            return h('span', {
                style: { color, fontWeight: '700' },
                title: `我方累计战损(伤+死) / 累计开战兵力；共 ${row.loss_ratio_battles || 0} 场（双方兵力均 > 20000）`,
            }, pct.toFixed(1) + '%')
        }
    },
    {
        title: '负率',
        key: 'loss_rate',
        width: 80,
        align: 'center',
        render(row) {
            const rate = row.total_battles > 0 ? Math.round(row.loss_count / row.total_battles * 1000) / 10 : 0
            return h('span', { style: { color: lossRateColor(rate), fontWeight: '700' } }, rate + '%')
        }
    },
    {
        title: '平局率',
        key: 'draw_rate',
        width: 80,
        align: 'center',
        render(row) {
            const rate = row.total_battles > 0 ? Math.round(row.draw_count / row.total_battles * 1000) / 10 : 0
            return h('span', { style: { fontWeight: '700' } }, rate + '%')
        }
    },
    {
        title: '最近战斗',
        key: 'last_time',
        width: 140,
        render(row) {
            return row.formatted_time
        }
    },
    {
        title: '队伍ID',
        key: 'idu',
        width: 100,
        ellipsis: { tooltip: true },
    },
    {
        // 展开这支队伍参与过的原始战报（明细在弹窗里，避免表格横向挤出屏幕）
        title: '操作',
        key: 'actions',
        width: 90,
        fixed: 'right',
        render(row) {
            return h(NButton, {
                size: 'tiny',
                quaternary: true,
                onClick: () => openRelatedBattles(row),
            }, { default: () => '战报', icon: () => h(ScrollText, { size: 14 }) })
        }
    },
]

const teamColumns: any[] = [
    {
        title: '队伍',
        key: 'heroes',
        minWidth: 200,
        render(row) {
            return row.team_names
        }
    },
    {
        title: '玩家',
        key: 'players',
        width: 160,
        ellipsis: { tooltip: true },
    },
    {
        title: '战法',
        key: 'skills',
        width: 200,
        render(row) {
            const lines = (row.parsed_skill_info || []).map(g => {
                const names = g.skills.slice(1).filter(s => s.id && s.id !== '0').map(s => s.name || getSkillName(s.id))
                return names.join('/')
            }).filter(Boolean)
            return h('div', { style: { whiteSpace: 'pre-line' } }, lines.join('\n'))
        }
    },
    {
        title: '总场次',
        key: 'total_battles',
        width: 80,
        align: 'center',
        sorter: (a, b) => a.total_battles - b.total_battles,
    },
    {
        title: '胜',
        key: 'win_count',
        width: 60,
        align: 'center',
        sorter: (a, b) => a.win_count - b.win_count,
    },
    {
        title: '负',
        key: 'loss_count',
        width: 60,
        align: 'center',
        sorter: (a, b) => a.loss_count - b.loss_count,
    },
    {
        title: '平',
        key: 'draw_count',
        width: 60,
        align: 'center',
        sorter: (a, b) => a.draw_count - b.draw_count,
    },
    {
        title: '胜率',
        key: 'win_rate',
        width: 80,
        align: 'center',
        sorter: (a, b) => a.win_rate - b.win_rate,
        defaultSortOrder: 'descend',
        render(row) {
            const rate = row.win_rate || 0
            return h('span', { style: { color: winRateColor(rate), fontWeight: '700' } }, rate + '%')
        }
    },
    {
        // 战损比 = 对方累计战损 / 我方累计战损，> 1 表示我方赚。
        // 战损 = 伤兵 + 死兵：这一场被打掉多少兵就算多少损失，伤兵战后恢复也算本场损耗。
        // 只统计双方兵力都 > 20000 的场次（完美克制时一方可能只带几十兵，
        // 比值会被极端放大到几百倍），且先按队伍累加再相除。
        title: '战损比',
        key: 'loss_ratio',
        width: 90,
        align: 'center',
        sorter: (a, b) => (a.loss_ratio || 0) - (b.loss_ratio || 0),
        render(row) {
            const ratio = row.loss_ratio || 0
            if (!ratio) {
                return h('span', { style: { color: '#bbb' } }, '—')
            }
            const color = ratio >= 1 ? '#18a058' : '#d03050'
            return h('span', {
                style: { color, fontWeight: '700' },
                title: `战损(伤+死) 我方 ${fmtHp(row.our_lost_hp)} / 对方 ${fmtHp(row.enemy_lost_hp)}；`
                    + `其中死兵 我方 ${fmtHp(row.our_killed_hp)} / 对方 ${fmtHp(row.enemy_killed_hp)}；`
                    + `统计场次 ${row.loss_ratio_battles || 0}（双方兵力均 > 20000）`,
            }, ratio.toFixed(2))
        }
    },
    {
        // 损耗率 = 我方累计战损（伤+死）/ 我方累计开战兵力（历史累计，与战损比同一批场次）。
        // 因为分子必然 <= 分母，累计损耗率一定 <= 100%；渲染时再做一次钳制兜底。
        // 注意：字段名必须是 destroyed_rate，不能叫 loss_rate ——
        // loss_rate 已被「负率」(loss_count/total_battles) 占用，两者撞名会导致
        // 损耗率列显示成负率的数值（例如负率 3.52% 被当成损耗率 352%）。
        title: '损耗率',
        key: 'destroyed_rate',
        width: 90,
        align: 'center',
        sorter: (a, b) => (a.destroyed_rate || 0) - (b.destroyed_rate || 0),
        render(row) {
            const rate = Number(row.destroyed_rate || 0)
            if (!rate) {
                return h('span', { style: { color: '#bbb' } }, '—')
            }
            // 兜底钳制：比值口径上不会超过 1，真出现异常也不显示 >100%
            const pct = Math.min(rate, 1) * 100
            const color = pct >= 60 ? '#d03050' : pct >= 30 ? '#f59e0b' : '#18a058'
            return h('span', {
                style: { color, fontWeight: '700' },
                title: `我方累计战损(伤+死) / 累计开战兵力；共 ${row.loss_ratio_battles || 0} 场（双方兵力均 > 20000）`,
            }, pct.toFixed(1) + '%')
        }
    },
    {
        title: '负率',
        key: 'loss_rate',
        width: 80,
        align: 'center',
        render(row) {
            const rate = row.total_battles > 0 ? Math.round(row.loss_count / row.total_battles * 1000) / 10 : 0
            return h('span', { style: { color: lossRateColor(rate), fontWeight: '700' } }, rate + '%')
        }
    },
    {
        title: '平局率',
        key: 'draw_rate',
        width: 80,
        align: 'center',
        render(row) {
            const rate = row.total_battles > 0 ? Math.round(row.draw_count / row.total_battles * 1000) / 10 : 0
            return h('span', { style: { fontWeight: '700' } }, rate + '%')
        }
    },
    {
        title: '最近战斗',
        key: 'last_time',
        width: 140,
        render(row) {
            return row.formatted_time
        }
    },
    {
        // 按队伍组合口径没有单一玩家，按三武将查所有参与过该阵容的战报
        title: '操作',
        key: 'actions',
        width: 90,
        fixed: 'right',
        render(row) {
            return h(NButton, {
                size: 'tiny',
                quaternary: true,
                onClick: () => openRelatedBattles(row),
            }, { default: () => '战报', icon: () => h(ScrollText, { size: 14 }) })
        }
    },
]

const currentColumns = computed(() => groupByPlayer.value ? playerColumns : teamColumns)
</script>

<template>
    <div class="page-team-winrate">
        <n-card class="page-card" embedded>
            <div class="page-header">
                <div class="page-header-info">
                    <h2 class="page-title">队伍胜率</h2>
                    <p class="page-desc">统计队伍组合的战斗胜率（攻方胜: 1/2/3/4/10/18/19，攻方负: 0，平局: 6/7/8/13）</p>
                </div>
            </div>

            <div class="search-bar">
                <n-input v-model:value="searchName" placeholder="玩家名称" clearable @keyup.enter="doSearch()" />
                <n-input v-model:value="searchUnion" placeholder="同盟名称" clearable @keyup.enter="doSearch()" />
                <n-input v-model:value="searchIdu" placeholder="队伍 ID" clearable @keyup.enter="doSearch()" />
                <n-button type="primary" @click="doSearch()" :loading="loading">
                    <template #icon><Search :size="16" /></template>
                    查询
                </n-button>
                <n-button quaternary :type="groupByPlayer ? 'primary' : 'default'" @click="groupByPlayer = !groupByPlayer">
                    <template #icon><Users :size="16" /></template>
                    {{ groupByPlayer ? '按玩家' : '按队伍' }}
                </n-button>
                <n-button quaternary :type="useImageMode ? 'primary' : 'default'" @click="useImageMode = !useImageMode">
                    <template #icon><Image :size="16" /></template>
                    {{ useImageMode ? '图片' : '表格' }}
                </n-button>
                <n-button quaternary @click="rebuildStats()" :loading="rebuilding">
                    <template #icon><RefreshCw :size="16" /></template>
                    重建索引
                </n-button>
            </div>
            <div class="filter-bar">
                <div class="filter-item">
                    <span class="filter-label">最低等级</span>
                    <n-input-number v-model:value="minLevel" :min="1" :max="50" style="width: 100px;" />
                </div>
                <div class="filter-item">
                    <span class="filter-label">最低兵力</span>
                    <n-input-number v-model:value="minHp" :min="0" :max="99999" :step="1000" style="width: 130px;" />
                </div>
            </div>

            <div class="pagination-wrap" v-if="total > pageSize">
                <n-pagination
                    v-model:page="page"
                    :page-size="pageSize"
                    :item-count="total"
                    :on-update:page="(p) => doSearch(p)"
                />
            </div>

            <div class="result-area" v-if="loading">
                <div class="loading-wrap">
                    <n-spin size="medium" />
                    <span>查询中...</span>
                </div>
            </div>

            <div class="result-area" v-else-if="hasSearched && results.length === 0">
                <n-empty description="未找到队伍数据" style="padding: 60px 0;" />
            </div>

            <div class="result-area" v-else-if="results.length > 0">
                <div class="result-summary">
                    共 <strong>{{ total }}</strong> {{ groupByPlayer ? '条记录' : '支队伍' }}
                    <span v-if="queryMs !== null">耗时 {{ queryMs }}ms</span>
                    <span v-if="cacheHit">命中缓存</span>
                    <span v-if="source === 'materialized'">统计索引</span>
                    <span v-else-if="source === 'raw'">原始查询</span>
                    <span v-if="!statsReady">索引未就绪</span>
                    <span v-if="rebuildProgressText">{{ rebuildProgressText }}</span>
                </div>

                <!-- 表格模式 -->
                <template v-if="!useImageMode">
                    <n-data-table
                        :columns="currentColumns"
                        :data="tableData"
                        :bordered="false"
                        size="small"
                        :scroll-x="groupByPlayer ? 1410 : 1310"
                    />
                </template>

                <!-- 大图模式 按玩家 -->
                <template v-else-if="groupByPlayer">
                    <div class="player-section" v-for="(teams, playerName) in groupedResults" :key="playerName">
                        <div class="player-name">
                            <Swords :size="16" />
                            {{ playerName }}
                        </div>

                        <div class="team-card" v-for="team in teams" :key="playerName + team.hero1_id + team.hero2_id + team.hero3_id">
                            <div class="team-header">
                                <span class="team-idu">{{ team.player_name }} · ID {{ team.idu }}</span>
                                <span class="team-time">{{ team.formatted_time }}</span>
                                <n-button size="tiny" quaternary @click="openRelatedBattles(team)">
                                    <template #icon><ScrollText :size="14" /></template>
                                    战报
                                </n-button>
                            </div>

                            <div class="hero-row hero-row--big">
                                <div class="hero-big" v-for="hero in team.heroes" :key="hero.id">
                                    <div class="hero-big-img">
                                        <img v-if="hero.id"
                                            :src="hero.imageUrl"
                                            @error="($event.target as any).style.display='none'" />
                                        <div class="hero-placeholder" v-else>?</div>
                                        <div class="hero-big-stars">
                                            <span v-for="s in hero.star" :key="'r'+s" class="hero-big-star-dot hero-big-star-dot--red"></span>
                                            <span v-for="s in hero.emptyStar" :key="'n'+s" class="hero-big-star-dot hero-big-star-dot--empty"></span>
                                            </div>
                                        </div>
                                    <div class="hero-big-info">
                                        <div class="hero-big-header">
                                            <span class="hero-big-name">{{ hero.name }}</span>
                                            <span class="hero-big-meta">
                                                <span v-if="hero.country">{{ hero.country }}</span>
                                                <span v-if="hero.type">·{{ hero.type }}</span>
                                                <span class="hero-big-star">·{{ hero.star }}红</span>
                                            </span>
                                        </div>
                                        <div class="hero-big-skills" v-if="team.all_skill_info">
                                            <div class="hero-big-skill" v-for="(skill, si) in hero.skills" :key="si">
                                                <template v-if="skill && skill.id && skill.id !== '0'">
                                                    <n-tag v-if="skill.quality" size="tiny" :bordered="false" :type="skill.quality === 'S' ? 'warning' : skill.quality === 'A' ? 'info' : 'default'">{{ skill.quality }}</n-tag>
                                                    <n-tag v-if="skill.type" size="tiny" :bordered="false">{{ skill.type }}</n-tag>
                                                    <span class="hero-big-skill-name">{{ skill.name }}</span>
                                                </template>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="stats-bar">
                                <div class="stat-item">
                                    <span class="stat-label">总场次</span>
                                    <span class="stat-value">{{ team.total_battles }}</span>
                                </div>
                                <div class="stat-item stat-win">
                                    <span class="stat-label">胜</span>
                                    <span class="stat-value">{{ team.win_count }}</span>
                                </div>
                                <div class="stat-item stat-loss">
                                    <span class="stat-label">负</span>
                                    <span class="stat-value">{{ team.loss_count }}</span>
                                </div>
                                <div class="stat-item stat-draw">
                                    <span class="stat-label">平</span>
                                    <span class="stat-value">{{ team.draw_count }}</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-label">胜率</span>
                                    <span class="stat-value" :style="{ color: winRateColor(team.win_rate || 0), fontWeight: 700 }">{{ (team.win_rate || 0) }}%</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-label">战损比</span>
                                    <span
                                        class="stat-value"
                                        :title="`战损(伤+死) 我方 ${fmtHp(team.our_lost_hp)} / 对方 ${fmtHp(team.enemy_lost_hp)}；其中死兵 我方 ${fmtHp(team.our_killed_hp)} / 对方 ${fmtHp(team.enemy_killed_hp)}；统计场次 ${team.loss_ratio_battles || 0}（双方兵力均 > 20000）`"
                                        :style="team.loss_ratio
                                            ? { color: team.loss_ratio >= 1 ? '#18a058' : '#d03050', fontWeight: 700 }
                                            : { color: '#bbb' }"
                                        >{{ team.loss_ratio ? team.loss_ratio.toFixed(2) : '—' }}</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-label">损耗率</span>
                                    <span
                                        class="stat-value"
                                        :title="`我方累计战损(伤+死) / 累计开战兵力（历史累计）`"
                                        :style="team.destroyed_rate
                                            ? { color: team.destroyed_rate >= 0.6 ? '#d03050' : team.destroyed_rate >= 0.3 ? '#f59e0b' : '#18a058', fontWeight: 700 }
                                            : { color: '#bbb' }"
                                        >{{ team.destroyed_rate ? (Math.min(team.destroyed_rate, 1) * 100).toFixed(1) + '%' : '—' }}</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-label">负率</span>
                                    <span class="stat-value" :style="{ color: lossRateColor(team.loss_rate), fontWeight: 700 }">{{ team.loss_rate }}%</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-label">平局率</span>
                                    <span class="stat-value" :style="{ fontWeight: 700 }">{{ team.draw_rate }}%</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </template>

                <!-- 大图模式 按队伍组合 -->
                <template v-else>
                    <div class="team-card" v-for="(team, key) in results" :key="key">
                        <div class="team-header">
                            <span class="team-idu" v-if="team.players">玩家: {{ team.players }}</span>
                            <span class="team-time">{{ team.formatted_time }}</span>
                            <n-button size="tiny" quaternary @click="openRelatedBattles(team)">
                                <template #icon><ScrollText :size="14" /></template>
                                战报
                            </n-button>
                        </div>

                        <div class="hero-row hero-row--big">
                            <div class="hero-big" v-for="hero in team.heroes" :key="hero.id">
                                <div class="hero-big-img">
                                    <img v-if="hero.id"
                                        :src="hero.imageUrl"
                                        @error="($event.target as any).style.display='none'" />
                                    <div class="hero-placeholder" v-else>?</div>
                                </div>
                                <div class="hero-big-info">
                                    <div class="hero-big-header">
                                        <span class="hero-big-name">{{ hero.name }}</span>
                                        <span class="hero-big-meta">
                                            <span v-if="hero.country">{{ hero.country }}</span>
                                            <span v-if="hero.type">·{{ hero.type }}</span>
                                        </span>
                                    </div>
                                    <div class="hero-big-skills" v-if="team.all_skill_info">
                                        <div class="hero-big-skill" v-for="(skill, si) in hero.skills" :key="si">
                                            <template v-if="skill && skill.id && skill.id !== '0'">
                                                <n-tag v-if="skill.quality" size="tiny" :bordered="false" :type="skill.quality === 'S' ? 'warning' : skill.quality === 'A' ? 'info' : 'default'">{{ skill.quality }}</n-tag>
                                                <n-tag v-if="skill.type" size="tiny" :bordered="false">{{ skill.type }}</n-tag>
                                                <span class="hero-big-skill-name">{{ skill.name }}</span>
                                            </template>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="stats-bar">
                            <div class="stat-item">
                                <span class="stat-label">总场次</span>
                                <span class="stat-value">{{ team.total_battles }}</span>
                            </div>
                            <div class="stat-item stat-win">
                                <span class="stat-label">胜</span>
                                <span class="stat-value">{{ team.win_count }}</span>
                            </div>
                            <div class="stat-item stat-loss">
                                <span class="stat-label">负</span>
                                <span class="stat-value">{{ team.loss_count }}</span>
                            </div>
                            <div class="stat-item stat-draw">
                                <span class="stat-label">平</span>
                                <span class="stat-value">{{ team.draw_count }}</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">胜率</span>
                                <span class="stat-value" :style="{ color: winRateColor(team.win_rate || 0), fontWeight: 700 }">{{ (team.win_rate || 0) }}%</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">战损比</span>
                                <span
                                    class="stat-value"
                                    :title="`战损(伤+死) 我方 ${fmtHp(team.our_lost_hp)} / 对方 ${fmtHp(team.enemy_lost_hp)}；其中死兵 我方 ${fmtHp(team.our_killed_hp)} / 对方 ${fmtHp(team.enemy_killed_hp)}；统计场次 ${team.loss_ratio_battles || 0}（双方兵力均 > 20000）`"
                                    :style="team.loss_ratio
                                        ? { color: team.loss_ratio >= 1 ? '#18a058' : '#d03050', fontWeight: 700 }
                                        : { color: '#bbb' }"
                                    >{{ team.loss_ratio ? team.loss_ratio.toFixed(2) : '—' }}</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">损耗率</span>
                                <span
                                    class="stat-value"
                                    :title="`我方累计战损(伤+死) / 累计开战兵力（历史累计）`"
                                    :style="team.destroyed_rate
                                        ? { color: team.destroyed_rate >= 0.6 ? '#d03050' : team.destroyed_rate >= 0.3 ? '#f59e0b' : '#18a058', fontWeight: 700 }
                                        : { color: '#bbb' }"
                                    >{{ team.destroyed_rate ? (Math.min(team.destroyed_rate, 1) * 100).toFixed(1) + '%' : '—' }}</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">负率</span>
                                <span class="stat-value" :style="{ color: lossRateColor(team.loss_rate), fontWeight: 700 }">{{ team.loss_rate }}%</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">平局率</span>
                                <span class="stat-value" :style="{ fontWeight: 700 }">{{ team.draw_rate }}%</span>
                            </div>
                        </div>
                    </div>
                </template>

            </div>
        </n-card>

        <!-- 原始战报明细 -->
        <n-modal v-model:show="battleModalVisible" preset="card" :title="`相关战报 · ${battleModalTitle}`" style="width: min(880px, calc(100vw - 48px))" to="body">
            <div class="battle-modal-body">
                <div class="battle-modal-summary">
                    共 <strong>{{ battleTotal }}</strong> 条战报<span v-if="battleTotal > battleList.length">（显示最近 {{ battleList.length }} 条）</span>
                </div>
                <div class="battle-modal-note">
                    每场战后：<b>剩余兵力 + 伤兵 + 死兵 = 开战兵力</b>。
                    <b>战损</b> = 伤兵 + 死兵 = 开战兵力 - 剩余兵力，即这一场被打掉的全部兵力
                    （伤兵战后能恢复，但本场确实损失了）。「战损比」= 对方战损 / 我方战损。
                    标有 <n-tag size="tiny" type="warning" :bordered="false">未计入</n-tag>
                    的场次因双方兵力未都超过 20000，<b>不参与</b>表格里的累计战损比与损耗率。
                </div>
                <div v-if="battleLoading" class="battle-loading">
                    <n-spin size="small" />
                    <span>加载中...</span>
                </div>
                <n-empty v-else-if="battleList.length === 0" description="这支队伍暂无战报" style="padding: 40px 0;" />
                <div v-else class="battle-list">
                    <div class="battle-item" v-for="battle in battleList" :key="battle.battle_id" @click="toggleBattleExpand(battle.battle_id)">
                        <div class="battle-item-head">
                            <n-tag size="tiny" :type="resultType(battle.result_label)" :bordered="false">{{ battle.result_label }}</n-tag>
                            <n-tag size="tiny" :bordered="false">{{ roleLabel(battle.role) }}</n-tag>
                            <span class="battle-time">{{ formatTime(battle.time) }}</span>
                            <span class="battle-opponent">对手 {{ battle.opponent_name || '-' }}</span>
                            <n-tag v-if="!battle.counted_in_loss_ratio" size="tiny" type="warning" :bordered="false" title="双方兵力未都超过 20000，不参与累计战损比">未计入</n-tag>
                            <span class="battle-loss">
                                战损(伤+死) 我 {{ battle.our_lost_hp.toLocaleString() }} : 敌 {{ battle.enemy_lost_hp.toLocaleString() }}
                                <span class="battle-ratio" v-if="battle.loss_ratio">· 战损比 {{ battle.loss_ratio.toFixed(2) }}</span>
                            </span>
                            <span class="battle-expand">{{ expandedBattles[battle.battle_id] ? '收起' : '明细' }}</span>
                        </div>

                        <div v-if="expandedBattles[battle.battle_id]" class="battle-detail">
                            <div class="battle-side" v-for="side in [
                                { key: 'our', label: '我方（' + roleLabel(battle.role) + '）', heroes: battle.role === 'defend' ? battle.defend_heroes : battle.attack_heroes },
                                { key: 'enemy', label: '对方', heroes: battle.role === 'defend' ? battle.attack_heroes : battle.defend_heroes },
                            ]" :key="side.key">
                                <div class="battle-side-title">{{ side.label }}</div>
                                <table class="loss-table">
                                    <thead>
                                        <tr>
                                            <th>武将</th>
                                            <th>等级</th>
                                            <th>开战兵力</th>
                                            <th>伤兵</th>
                                            <th>死兵（永久）</th>
                                            <th>战损</th>
                                            <th>剩余</th>
                                            <th>损耗率</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="hero in side.heroes" :key="side.key + hero.hero_id">
                                            <td class="loss-hero">{{ getHeroName(hero.hero_id) }}</td>
                                            <td>{{ hero.level }}</td>
                                            <td>{{ hero.total_hp.toLocaleString() }}</td>
                                            <td class="loss-wounded">{{ hero.wounded.toLocaleString() }}</td>
                                            <td class="loss-killed">{{ hero.killed.toLocaleString() }}</td>
                                            <td class="loss-total">{{ hero.lost_hp.toLocaleString() }}</td>
                                            <td>{{ hero.remain_hp.toLocaleString() }}</td>
                                            <td :style="{ color: hero.loss_ratio >= 0.7 ? '#d03050' : hero.loss_ratio >= 0.4 ? '#f59e0b' : '#18a058', fontWeight: 600 }">
                                                {{ (hero.loss_ratio * 100).toFixed(1) }}%
                                            </td>
                                        </tr>
                                        <tr v-if="!side.heroes || side.heroes.length === 0">
                                            <td colspan="8" class="loss-empty">无明细数据</td>
                                        </tr>
                                    </tbody>
                                    <tfoot v-if="side.heroes && side.heroes.length">
                                        <tr>
                                            <td colspan="2" class="loss-foot-label">合计</td>
                                            <td>{{ side.heroes.reduce((s, h) => s + h.total_hp, 0).toLocaleString() }}</td>
                                            <td class="loss-wounded">{{ side.heroes.reduce((s, h) => s + h.wounded, 0).toLocaleString() }}</td>
                                            <td class="loss-killed">{{ side.heroes.reduce((s, h) => s + h.killed, 0).toLocaleString() }}</td>
                                            <td class="loss-total">{{ side.heroes.reduce((s, h) => s + h.lost_hp, 0).toLocaleString() }}</td>
                                            <td>{{ side.heroes.reduce((s, h) => s + h.remain_hp, 0).toLocaleString() }}</td>
                                            <td>
                                                {{ (side.heroes.reduce((s, h) => s + h.total_hp, 0) > 0
                                                    ? side.heroes.reduce((s, h) => s + h.lost_hp, 0) / side.heroes.reduce((s, h) => s + h.total_hp, 0) * 100
                                                    : 0).toFixed(1) }}%
                                            </td>
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </n-modal>
    </div>
</template>

<style scoped lang="scss">
.page-team-winrate {
    display: flex;
    flex-direction: column;
}

.page-card {
    border-radius: 12px;
    overflow: hidden;
}

.page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
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

.search-bar {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.search-bar .n-input {
    flex: 1;
    min-width: 160px;
}

.filter-bar {
    display: flex;
    gap: 20px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.filter-item {
    display: flex;
    align-items: center;
    gap: 8px;
}

.filter-label {
    font-size: 13px;
    color: var(--color-text-secondary);
    white-space: nowrap;
}

.result-area {
    min-height: 200px;
    overflow-x: auto;
}

.loading-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 60px 0;
    color: var(--color-text-secondary);
    font-size: 14px;
}

.result-summary {
    font-size: 13px;
    color: var(--color-text-secondary);
    margin-bottom: 16px;
}

.pagination-wrap {
    display: flex;
    justify-content: center;
    margin-top: 20px;
    padding: 16px 0;
}

.player-section {
    margin-bottom: 24px;
}

.player-name {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 700;
    color: var(--color-text);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--color-border);
}

.team-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    transition: box-shadow 0.2s;

    &:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    }
}

.team-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}

.team-idu {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: var(--color-text-secondary);
}

.team-time {
    margin-left: auto;
    font-size: 12px;
    color: var(--color-text-secondary);
}

.battle-modal-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.battle-modal-summary {
    font-size: 13px;
    color: var(--color-text-secondary);
}

.battle-modal-note {
    font-size: 12px;
    line-height: 1.7;
    color: var(--color-text-secondary);
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.25);
    border-radius: 8px;
    padding: 8px 12px;

    b {
        color: var(--color-text);
    }
}

.battle-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 40px 0;
    font-size: 13px;
    color: var(--color-text-secondary);
}

.battle-list {
    max-height: 60vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.battle-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px 12px;
    background: var(--color-bg);
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
}

.battle-item-head {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.battle-loss {
    margin-left: auto;
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
}

.battle-ratio {
    color: var(--color-text-secondary);
}

.battle-expand {
    color: #2080f0;
    font-size: 12px;
    white-space: nowrap;
}

.battle-detail {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 8px 0 4px;
    border-top: 1px dashed var(--color-border);
    cursor: default;
}

.battle-side-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin-bottom: 6px;
}

.loss-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-variant-numeric: tabular-nums;

    th,
    td {
        padding: 4px 8px;
        text-align: right;
        border-bottom: 1px solid var(--color-border);
    }

    th {
        font-weight: 600;
        color: var(--color-text-secondary);
        white-space: nowrap;
    }

    th:first-child,
    td:first-child {
        text-align: left;
    }
}

.loss-hero {
    color: var(--color-text);
    font-weight: 600;
    white-space: nowrap;
}

.loss-remain {
    color: #18a058;
}

.loss-wounded {
    color: #f59e0b;
}

.loss-killed {
    color: #d03050;
}

.loss-total {
    color: #d03050;
    font-weight: 700;
}

.loss-foot-label {
    text-align: right;
    color: var(--color-text-secondary);
    font-weight: 600;
}

.loss-empty {
    text-align: center;
    color: var(--color-text-secondary);
}

.battle-time {
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
}

.battle-opponent {
    color: var(--color-text);
}

.battle-hp {
    margin-left: auto;
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
}

.hero-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 16px;
}

.hero-big {
    display: flex;
    gap: 0;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 10px;
    overflow: hidden;

    &-img {
        position: relative;
        width: 160px;
        flex-shrink: 0;

        img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }
    }

    &-stars {
        position: absolute;
        top: 6px;
        right: 6px;
        display: flex;
        gap: 1px;
        padding: 3px 4px;
    }

    &-star-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.85);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);

        &--red {
            background: #ef4444;
        }

        &--empty {
            background: rgba(255, 255, 255, 0.7);
        }
    }

    &-info {
        flex: 1;
        min-width: 0;
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    &-header {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    &-name {
        font-size: 14px;
        font-weight: 700;
        color: var(--color-text);
    }

    &-meta {
        display: flex;
        align-items: center;
        gap: 2px;
        font-size: 11px;
        color: var(--color-text-secondary);
        flex-wrap: wrap;
    }

    &-star {
        color: #f59e0b;
    }

    &-skills {
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-top: 4px;
        max-height: 120px;
        overflow-y: auto;
        padding-right: 4px;
    }

    &-skill {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 11px;
    }

    &-skill-name {
        color: var(--color-text);
        font-size: 11px;
    }
}

.hero-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    color: var(--color-text-secondary);
}

.stats-bar {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 12px 16px;
    background: var(--color-bg);
    border-radius: 8px;
    flex-wrap: wrap;
}

.stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
}

.stat-label {
    font-size: 12px;
    color: var(--color-text-secondary);
}

.stat-value {
    font-size: 16px;
    font-weight: 600;
    color: var(--color-text);
}

.stat-win .stat-value {
    color: #22c55e;
}

.stat-loss .stat-value {
    color: #ef4444;
}

.stat-draw .stat-value {
    color: #f59e0b;
}
</style>
