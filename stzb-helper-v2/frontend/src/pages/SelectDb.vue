<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NButton, NEmpty, NSpin, NModal, NInput, NTag, NPopconfirm, useMessage } from 'naive-ui'
import { GetDbList, SelectDb, CreateDb, RenameDb, DeleteDb } from '../../wailsjs/go/main/App'
import { Database, ChevronRight, RefreshCw, Plus, Pencil, Trash2 } from 'lucide-vue-next'

const router = useRouter()
const nmessage = useMessage()
const dbList = ref<string[]>([])
const loading = ref(false)
const selecting = ref(false)
const selectedName = ref('')

const showCreateModal = ref(false)
const newDbName = ref('')
const creating = ref(false)

const showRenameModal = ref(false)
const renameSource = ref('')
const renameTarget = ref('')
const renaming = ref(false)

const deletingName = ref('')

const displayDbName = (name: string) => name.replace('[配置]', '')
const isConfigDb = (name: string) => name.startsWith('[配置]')

const loadDbList = () => {
    loading.value = true
    GetDbList().then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            dbList.value = resp.data || []
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('获取数据库列表失败: ' + e)
    }).finally(() => {
        loading.value = false
    })
}

const handleSelect = (name: string) => {
    selecting.value = true
    selectedName.value = name
    SelectDb(name).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            sessionStorage.setItem('selectedDb', name)
            nmessage.success(resp.msg)
            router.push('/')
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('连接数据库失败: ' + e)
    }).finally(() => {
        selecting.value = false
        selectedName.value = ''
    })
}

const handleCreate = () => {
    const name = newDbName.value.trim()
    if (!name) {
        nmessage.warning('请输入数据库名称')
        return
    }
    creating.value = true
    CreateDb(name).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            nmessage.success(resp.msg)
            sessionStorage.setItem('selectedDb', name)
            showCreateModal.value = false
            router.push('/')
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('创建数据库失败: ' + e)
    }).finally(() => {
        creating.value = false
    })
}

const openRenameModal = (name: string) => {
    renameSource.value = name
    renameTarget.value = displayDbName(name)
    showRenameModal.value = true
}

const handleRename = () => {
    const target = renameTarget.value.trim()
    if (!target) {
        nmessage.warning('请输入新的数据库名称')
        return
    }
    renaming.value = true
    RenameDb(renameSource.value, target).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            const nextSelectedName = isConfigDb(renameSource.value) ? `[配置]${target}` : target
            sessionStorage.setItem('selectedDb', nextSelectedName)
            nmessage.success(resp.msg)
            showRenameModal.value = false
            loadDbList()
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('重命名数据库失败: ' + e)
    }).finally(() => {
        renaming.value = false
    })
}

const handleDelete = (name: string) => {
    deletingName.value = name
    DeleteDb(name).then(v => {
        let resp = JSON.parse(v)
        if (resp.code == 200) {
            nmessage.success(resp.msg)
            loadDbList()
        } else {
            nmessage.error(resp.msg)
        }
    }).catch(e => {
        nmessage.error('删除数据库失败: ' + e)
    }).finally(() => {
        deletingName.value = ''
    })
}

onMounted(() => {
    loadDbList()
})
</script>

<template>
    <n-modal v-model:show="showCreateModal" preset="card" title="创建数据库" size="small"
        style="width: min(400px, calc(100vw - 48px))" :bordered="false" :mask-closable="false" to="body">
        <n-input v-model:value="newDbName" placeholder="请输入数据库名称" @keyup.enter="handleCreate" />
        <template #footer>
            <div class="modal-footer-actions">
                <n-button strong secondary type="primary" :loading="creating" @click="handleCreate">
                    创建并进入
                </n-button>
                <n-button strong secondary @click="showCreateModal = false">
                    取消
                </n-button>
            </div>
        </template>
    </n-modal>

    <n-modal v-model:show="showRenameModal" preset="card" title="重命名数据库" size="small"
        style="width: min(400px, calc(100vw - 48px))" :bordered="false" :mask-closable="false" to="body">
        <n-input v-model:value="renameTarget" placeholder="请输入新的数据库名称" @keyup.enter="handleRename" />
        <template #footer>
            <div class="modal-footer-actions">
                <n-button strong secondary type="primary" :loading="renaming" @click="handleRename">
                    保存名称
                </n-button>
                <n-button strong secondary @click="showRenameModal = false">
                    取消
                </n-button>
            </div>
        </template>
    </n-modal>

    <div class="select-db-page">
        <div class="select-db-container">
            <div class="select-db-header">
                <div class="select-db-icon">
                    <Database :size="28" />
                </div>
                <h1 class="select-db-title">数据库管理</h1>
                <p class="select-db-desc">在这里选择、创建、重命名或删除数据库</p>
            </div>

            <div class="select-db-actions">
                <n-button size="small" @click="loadDbList" :loading="loading">
                    <template #icon><RefreshCw :size="14" /></template>
                    重新扫描
                </n-button>
                <n-button size="small" type="primary" @click="showCreateModal = true">
                    <template #icon><Plus :size="14" /></template>
                    创建数据库
                </n-button>
            </div>

            <n-card class="select-db-card" embedded :bordered="false">
                <div class="db-list-loading" v-if="loading">
                    <n-spin size="medium" />
                    <span>正在扫描数据库文件...</span>
                </div>

                <div class="db-list" v-else-if="dbList.length > 0">
                    <div class="db-item" v-for="db in dbList" :key="db">
                        <div class="db-item-left">
                            <div class="db-item-icon">
                                <Database :size="18" />
                            </div>
                            <div class="db-item-info">
                                <span class="db-item-name">{{ displayDbName(db) }}</span>
                                <n-tag v-if="isConfigDb(db)" size="small" type="info">当前默认</n-tag>
                            </div>
                        </div>
                        <div class="db-item-right">
                            <n-button size="tiny" quaternary @click="handleSelect(db)"
                                :loading="selecting && selectedName === db">
                                <template #icon><ChevronRight :size="14" /></template>
                                进入
                            </n-button>
                            <n-button size="tiny" quaternary @click="openRenameModal(db)">
                                <template #icon><Pencil :size="14" /></template>
                                改名
                            </n-button>
                            <n-popconfirm @positive-click="handleDelete(db)" :show-icon="false">
                                <template #trigger>
                                    <n-button size="tiny" quaternary type="error" :loading="deletingName === db">
                                        <template #icon><Trash2 :size="14" /></template>
                                        删除
                                    </n-button>
                                </template>
                                {{ isConfigDb(db) ? '当前默认数据库不能直接删除，请先切换到其他数据库。' : `确认删除数据库 ${displayDbName(db)} 吗？` }}
                            </n-popconfirm>
                        </div>
                    </div>
                </div>

                <n-empty v-else description="未找到数据库文件" style="padding: 32px 0;" />
            </n-card>
        </div>
    </div>
</template>

<style scoped lang="scss">
.select-db-page {
    display: flex;
    align-items: flex-start;
    justify-content: center;
    min-height: 100%;
    padding-top: 80px;
    background: var(--color-bg);
}

.select-db-container {
    width: 100%;
    max-width: 720px;
}

.select-db-header {
    text-align: center;
    margin-bottom: 24px;
}

.select-db-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 14px;
    background: linear-gradient(135deg, #404040, #171717);
    color: #fff;
    margin-bottom: 16px;
}

.select-db-title {
    font-size: 22px;
    font-weight: 700;
    color: var(--color-text);
    margin: 0 0 6px;
}

.select-db-desc {
    font-size: 14px;
    color: var(--color-text-secondary);
    margin: 0;
}

.select-db-card {
    border-radius: 12px;
}

.db-list-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 40px 0;
    color: var(--color-text-secondary);
    font-size: 14px;
}

.db-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.db-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 14px 16px;
    border-radius: 10px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
}

.db-item-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
}

.db-item-info {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.db-item-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: var(--color-primary-light);
    color: var(--color-accent);
}

.db-item-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--color-text);
    word-break: break-all;
}

.db-item-right {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
    justify-content: flex-end;
}

.select-db-actions {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-bottom: 16px;
}

.modal-footer-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
}
</style>
