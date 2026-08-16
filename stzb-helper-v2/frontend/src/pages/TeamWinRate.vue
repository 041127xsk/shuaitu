<script setup lang="ts">
import { ref, computed, h, watch, onMounted, onUnmounted } from 'vue'
import { NCard, NButton, NInput, NInputNumber, NEmpty, NSpin, NTag, NPagination, NDataTable, useMessage } from 'naive-ui'
import { GetMaterializedStatsStatus, GetTeamWinRate, GetTeamWinRateByTeam, RebuildMaterializedStats } from '../../wailsjs/go/main/App'
import { Search, Image, Users, RefreshCw } from 'lucide-vue-next'
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
                        :scroll-x="groupByPlayer ? 1320 : 1220"
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
