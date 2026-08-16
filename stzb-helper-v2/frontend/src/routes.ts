import { createRouter, createWebHashHistory, type RouteLocationNormalized, type NavigationGuardNext } from 'vue-router'
import { CheckNpcap } from '../wailsjs/go/main/App'

const Index = () => import('./pages/Index.vue')
const TeamUser = () => import('./pages/TeamUser.vue')
const Task = () => import('./pages/Task.vue')
const AutoScroll = () => import('./pages/AutoScroll.vue')
const GroupWu = () => import('./pages/GroupWu.vue')
const SelectDb = () => import('./pages/SelectDb.vue')
const Logs = () => import('./pages/Logs.vue')
const NpcapHelp = () => import('./pages/NpcapHelp.vue')
const Debug = () => import('./pages/Debug.vue')
const TeamQuery = () => import('./pages/TeamQuery.vue')
const Book = () => import('./pages/Book.vue')
const TeamWinRate = () => import('./pages/TeamWinRate.vue')

const routes = [
    {
        path: '/',
        name: 'index',
        component: Index,
        meta: { title: '控制面板' }
    },
    {
        path: '/teamuser',
        name: 'teamuser',
        component: TeamUser,
        meta: { title: '同盟成员' }
    },
    {
        path: '/task',
        name: 'task',
        component: Task,
        meta: { title: '攻城任务' }
    },
    {
        path: '/autoscroll',
        name: 'autoscroll',
        component: AutoScroll,
        meta: { title: '自动翻页' }
    },
    {
        path: '/groupWu',
        name: 'groupWu',
        component: GroupWu,
        meta: { title: '分组武勋' }
    },
    {
        path: '/select-db',
        name: 'selectDb',
        component: SelectDb,
        meta: { title: '选择数据库' }
    },
    {
        path: '/logs',
        name: 'logs',
        component: Logs,
        meta: { title: '运行日志' }
    },
    {
        path: '/npcap-help',
        name: 'npcapHelp',
        component: NpcapHelp,
        meta: { title: '安装 Npcap' }
    },
    {
        path: '/debug',
        name: 'debug',
        component: Debug,
        meta: { title: 'API 调试' }
    },
    {
        path: '/teamquery',
        name: 'teamquery',
        component: TeamQuery,
        meta: { title: '队伍查询' }
    },
    {
        path: '/teamwinrate',
        name: 'teamwinrate',
        component: TeamWinRate,
        meta: { title: '队伍胜率' }
    },
    {
        path: '/book',
        name: 'book',
        component: Book,
        meta: { title: '主公簿' }
    },
]

const router = createRouter({
    history: createWebHashHistory(),
    routes,
})

let npcapChecked = false
let npcapInstalled = false

router.beforeEach(async (to: RouteLocationNormalized, _from: RouteLocationNormalized, next: NavigationGuardNext) => {
    if (to.name === 'npcapHelp') {
        next()
        return
    }

    if (!npcapChecked) {
        try {
            const resp = JSON.parse(await CheckNpcap())
            npcapInstalled = resp.code == 200 && resp.data.installed
        } catch {
            npcapInstalled = false
        }
        npcapChecked = true
    }

    if (!npcapInstalled) {
        next({ name: 'npcapHelp' })
        return
    }

    const selectedDb = sessionStorage.getItem('selectedDb')
    if (to.name !== 'selectDb' && !selectedDb) {
        next({ name: 'selectDb' })
    } else {
        next()
    }
})

export default router
