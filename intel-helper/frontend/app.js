/**
 * 率土战报情报库 - 前端应用脚本
 */

// ============================================================================
// 全局状态
// ============================================================================

const API_BASE = '';
let currentUploadResult = null;
let currentPlayerId = null;
let currentHeroes = [];

// ============================================================================
// 工具函数
// ============================================================================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ============================================================================
// 页面导航
// ============================================================================

function showPage(pageName) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const page = document.getElementById(`page-${pageName}`);
    const btn = document.querySelector(`.nav-btn[data-page="${pageName}"]`);

    if (page) page.classList.add('active');
    if (btn) btn.classList.add('active');

    // 加载页面数据
    if (pageName === 'search') {
        loadSeasons();
    } else if (pageName === 'heroes') {
        loadHeroes();
    } else if (pageName === 'teams') {
        loadTeams();
    }
}

// ============================================================================
// 上传战报
// ============================================================================

function initUpload() {
    const uploadBox = document.getElementById('upload-box');
    const fileInput = document.getElementById('file-input');
    const btnUpload = document.getElementById('btn-upload');

    // 点击上传框
    uploadBox.addEventListener('click', () => fileInput.click());

    // 拖拽上传
    uploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadBox.classList.add('dragover');
    });

    uploadBox.addEventListener('dragleave', () => {
        uploadBox.classList.remove('dragover');
    });

    uploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadBox.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateUploadUI();
        }
    });

    // 文件选择
    fileInput.addEventListener('change', updateUploadUI);

    // 上传按钮
    btnUpload.addEventListener('click', handleUpload);
}

function updateUploadUI() {
    const fileInput = document.getElementById('file-input');
    const btnUpload = document.getElementById('btn-upload');
    const seasonInput = document.getElementById('season-input');

    btnUpload.disabled = !fileInput.files[0] || !seasonInput.value.trim();
}

async function handleUpload() {
    const fileInput = document.getElementById('file-input');
    const seasonInput = document.getElementById('season-input');
    const btnUpload = document.getElementById('btn-upload');

    const file = fileInput.files[0];
    const season = seasonInput.value.trim();

    if (!file) {
        showToast('请选择图片文件', 'error');
        return;
    }

    if (!season) {
        showToast('请输入赛季', 'error');
        return;
    }

    btnUpload.disabled = true;
    btnUpload.textContent = '上传中...';

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('season', season);

        const response = await fetch(`${API_BASE}/intel/upload`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || '上传失败');
        }

        currentUploadResult = result;
        showOCRResult(result);

    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btnUpload.disabled = false;
        btnUpload.textContent = '上传并识别';
    }
}

function showOCRResult(result) {
    const ocrResult = document.getElementById('ocr-result');
    const previewImage = document.getElementById('preview-image');
    const rawOcrText = document.getElementById('raw-ocr-text');
    const confidenceBadge = document.getElementById('confidence-badge');
    const suggestPlayer = document.getElementById('suggest-player');
    const suggestAlliance = document.getElementById('suggest-alliance');
    const suggestHeroes = document.getElementById('suggest-heroes');

    // 显示图片
    previewImage.src = `${API_BASE}/screenshots/${result.image_path.split('/').pop()}`;

    // 显示原始OCR文本
    rawOcrText.textContent = result.raw_ocr_text || '(未能识别到文字)';

    // 显示置信度
    confidenceBadge.textContent = `置信度: ${result.confidence || 0}%`;

    // 显示建议数据
    suggestPlayer.value = result.suggested?.player_name || '';
    suggestAlliance.value = result.suggested?.alliance || '';

    // 显示武将标签
    suggestHeroes.innerHTML = '';
    const heroes = result.suggested?.heroes || [];
    if (heroes.length === 0) {
        suggestHeroes.innerHTML = '<span style="color: var(--text-secondary);">未识别到武将</span>';
    } else {
        heroes.forEach(hero => {
            const tag = document.createElement('span');
            tag.className = 'hero-tag';
            tag.textContent = hero;
            suggestHeroes.appendChild(tag);
        });
    }

    ocrResult.style.display = 'block';
}

function initConfirm() {
    const btnConfirm = document.getElementById('btn-confirm');
    const btnSaveConfirm = document.getElementById('btn-save-confirm');

    btnConfirm.addEventListener('click', openConfirmModal);
    btnSaveConfirm.addEventListener('click', handleSaveConfirm);

    // 赛季输入同步
    const seasonInput = document.getElementById('season-input');
    const confirmSeason = document.getElementById('confirm-season');
    seasonInput.addEventListener('input', () => {
        confirmSeason.value = seasonInput.value;
    });
}

function openConfirmModal() {
    if (!currentUploadResult) {
        showToast('请先上传战报', 'error');
        return;
    }

    const suggestPlayer = document.getElementById('suggest-player');
    const suggestAlliance = document.getElementById('suggest-alliance');
    const seasonInput = document.getElementById('season-input');

    document.getElementById('confirm-player-name').value = suggestPlayer.value;
    document.getElementById('confirm-alliance').value = suggestAlliance.value;
    document.getElementById('confirm-season').value = seasonInput.value;

    // 填充武将
    const heroes = currentUploadResult.suggested?.heroes || [];
    for (let i = 0; i < 3; i++) {
        document.getElementById(`hero-${i + 1}`).value = heroes[i] || '';
    }

    document.getElementById('confirm-modal').classList.add('show');
}

function closeModal() {
    document.getElementById('confirm-modal').classList.remove('show');
}

async function handleSaveConfirm() {
    const playerName = document.getElementById('confirm-player-name').value.trim();
    const alliance = document.getElementById('confirm-alliance').value.trim();
    const server = document.getElementById('confirm-server').value.trim();
    const season = document.getElementById('confirm-season').value.trim();
    const enemySide = document.getElementById('confirm-enemy-side').value;
    const battleResult = document.getElementById('confirm-battle-result').value;
    const notes = document.getElementById('confirm-notes').value.trim();

    if (!playerName) {
        showToast('玩家名不能为空', 'error');
        return;
    }

    if (!season) {
        showToast('赛季不能为空', 'error');
        return;
    }

    // 收集武将
    const heroes = [];
    for (let i = 1; i <= 3; i++) {
        const heroName = document.getElementById(`hero-${i}`).value.trim();
        if (heroName) {
            heroes.push({
                name: heroName,
                position: i
            });
        }
    }

    const btnSaveConfirm = document.getElementById('btn-save-confirm');
    btnSaveConfirm.disabled = true;
    btnSaveConfirm.textContent = '保存中...';

    try {
        const response = await fetch(`${API_BASE}/intel/confirm`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                snapshot_id: currentUploadResult.snapshot_id,
                player_name: playerName,
                season: season,
                alliance: alliance || null,
                server: server || null,
                heroes: heroes,
                enemy_side: enemySide,
                battle_result: battleResult,
                notes: notes || null
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || '保存失败');
        }

        showToast('情报保存成功', 'success');
        closeModal();

        // 重置上传区域
        resetUploadArea();

    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btnSaveConfirm.disabled = false;
        btnSaveConfirm.textContent = '保存';
    }
}

function resetUploadArea() {
    document.getElementById('file-input').value = '';
    document.getElementById('season-input').value = '';
    document.getElementById('ocr-result').style.display = 'none';
    currentUploadResult = null;
    updateUploadUI();
}

// ============================================================================
// 搜索玩家
// ============================================================================

async function loadSeasons() {
    try {
        const response = await fetch(`${API_BASE}/seasons`);
        const data = await response.json();

        const select = document.getElementById('search-season');
        select.innerHTML = '<option value="">所有赛季</option>';

        data.seasons.forEach(season => {
            const option = document.createElement('option');
            option.value = season;
            option.textContent = season;
            select.appendChild(option);
        });

    } catch (error) {
        console.error('加载赛季失败:', error);
    }
}

// 所有玩家下拉菜单
let allPlayersData = [];
let expandedPlayerIds = new Set();

function initAllPlayersDropdown() {
    const btn = document.getElementById('btn-all-players');
    const panel = document.getElementById('all-players-panel');
    const filterInput = document.getElementById('players-filter');

    // 点击按钮切换面板
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = panel.classList.contains('show');
        if (isOpen) {
            panel.classList.remove('show');
        } else {
            panel.classList.add('show');
            if (allPlayersData.length === 0) {
                loadAllPlayers();
            }
        }
    });

    // 点击外部关闭面板
    document.addEventListener('click', (e) => {
        if (!panel.contains(e.target) && !btn.contains(e.target)) {
            panel.classList.remove('show');
        }
    });

    // 筛选玩家
    filterInput.addEventListener('input', () => {
        renderAllPlayers(filterInput.value.trim());
    });
}

async function loadAllPlayers() {
    const listEl = document.getElementById('all-players-list');
    const countEl = document.getElementById('players-count');

    try {
        const response = await fetch(`${API_BASE}/players/all`);
        const data = await response.json();

        allPlayersData = data.players || [];
        countEl.textContent = `(${allPlayersData.length})`;

        renderAllPlayers('');

    } catch (error) {
        console.error('加载玩家列表失败:', error);
        listEl.innerHTML = '<div class="dropdown-empty">加载失败，请重试</div>';
    }
}

function renderAllPlayers(filter) {
    const listEl = document.getElementById('all-players-list');

    if (allPlayersData.length === 0) {
        listEl.innerHTML = '<div class="dropdown-empty">暂无统计数据</div>';
        return;
    }

    const filtered = filter
        ? allPlayersData.filter(p => p.name.toLowerCase().includes(filter.toLowerCase()))
        : allPlayersData;

    if (filtered.length === 0) {
        listEl.innerHTML = '<div class="dropdown-empty">没有找到匹配的玩家</div>';
        return;
    }

    listEl.innerHTML = filtered.map(player => {
        const isExpanded = expandedPlayerIds.has(player.id);
        const teamsHtml = player.teams.map(team => {
            const heroesStr = team.heroes.join(' + ');
            const resultClass = team.battle_result === 'win' ? 'win' :
                               team.battle_result === 'loss' ? 'loss' : '';
            const resultText = team.battle_result === 'win' ? '胜' :
                               team.battle_result === 'loss' ? '负' :
                               team.battle_result === 'draw' ? '平' : '';

            return `
                <div class="player-team-item" onclick="loadPlayerDetail(${player.id})">
                    <span class="team-result ${resultClass}">${resultText}</span>
                    <span class="team-heroes">${heroesStr}</span>
                </div>
            `;
        }).join('');

        return `
            <div class="player-item">
                <div class="player-item-header" onclick="togglePlayerExpand(${player.id})">
                    <div class="player-item-info">
                        <span class="player-name">${player.name}</span>
                        <span class="player-meta">${player.season || ''} ${player.alliance ? '· ' + player.alliance : ''}</span>
                    </div>
                    <div class="player-item-right">
                        <span class="team-count">${player.team_count}队</span>
                        <span class="expand-icon ${isExpanded ? 'expanded' : ''}">▼</span>
                    </div>
                </div>
                <div class="player-item-teams" style="display: ${isExpanded ? 'block' : 'none'}">
                    ${teamsHtml || '<div class="no-teams">暂无队伍</div>'}
                </div>
            </div>
        `;
    }).join('');
}

function togglePlayerExpand(playerId) {
    if (expandedPlayerIds.has(playerId)) {
        expandedPlayerIds.delete(playerId);
    } else {
        expandedPlayerIds.add(playerId);
    }
    const filter = document.getElementById('players-filter').value.trim();
    renderAllPlayers(filter);
}

async function searchPlayers() {
    const searchInput = document.getElementById('search-input');
    const searchSeason = document.getElementById('search-season');
    const resultsList = document.getElementById('search-results');
    const btnSearch = document.getElementById('btn-search');

    const query = searchInput.value.trim();
    const season = searchSeason.value;

    // 显示加载状态
    btnSearch.disabled = true;
    btnSearch.innerHTML = '<span class="loading">🔍</span> 搜索中...';
    resultsList.innerHTML = '<div class="loading-state">⏳ 搜索中...</div>';

    try {
        const params = new URLSearchParams();
        if (query) params.append('q', query);
        if (season) params.append('season', season);

        const response = await fetch(`${API_BASE}/players/search?${params}`);
        const data = await response.json();

        resultsList.innerHTML = '';

        if (data.results.length === 0) {
            resultsList.innerHTML = `
                <div class="empty-state">
                    <p>没有找到玩家 "${query || '所有玩家'}"</p>
                </div>
            `;
            return;
        }

        data.results.forEach(player => {
            const item = document.createElement('div');
            item.className = 'result-item';
            item.onclick = () => loadPlayerDetail(player.id);

            item.innerHTML = `
                <div class="result-item-name">${player.name}</div>
                <div class="result-item-meta">
                    <span>同盟: ${player.alliance || '-'}</span>
                    <span>赛季: ${player.season}</span>
                    <span>队伍: ${player.team_count}</span>
                    <span>最近: ${formatDate(player.latest_seen)}</span>
                </div>
            `;

            resultsList.appendChild(item);
        });

    } catch (error) {
        showToast('搜索失败: ' + error.message, 'error');
        resultsList.innerHTML = '<div class="error-state">❌ 搜索失败，请重试</div>';
    } finally {
        btnSearch.disabled = false;
        btnSearch.innerHTML = '🔍 搜索';
    }
}

async function loadPlayerDetail(playerId) {
    try {
        const response = await fetch(`${API_BASE}/players/${playerId}`);
        const player = await response.json();

        currentPlayerId = playerId;
        showPlayerDetail(player);
        showPage('player');

    } catch (error) {
        showToast('加载玩家详情失败', 'error');
    }
}

function showPlayerDetail(player) {
    const playerInfo = document.getElementById('player-info');
    const playerTeams = document.getElementById('player-teams');

    playerInfo.innerHTML = `
        <h3>${player.name}</h3>
        <div class="player-info-grid">
            <div class="info-item">
                <label>同盟</label>
                <span>${player.alliance || '-'}</span>
            </div>
            <div class="info-item">
                <label>区服</label>
                <span>${player.server || '-'}</span>
            </div>
            <div class="info-item">
                <label>赛季</label>
                <span>${player.season}</span>
            </div>
            <div class="info-item">
                <label>队伍数</label>
                <span>${player.team_count}</span>
            </div>
            <div class="info-item">
                <label>创建时间</label>
                <span>${formatDate(player.created_at)}</span>
            </div>
            <div class="info-item">
                <label>更新时间</label>
                <span>${formatDate(player.updated_at)}</span>
            </div>
        </div>
        ${player.notes ? `<div class="info-item" style="margin-top: 16px;"><label>备注</label><span>${player.notes}</span></div>` : ''}
    `;

    if (player.teams.length === 0) {
        playerTeams.innerHTML = `
            <div class="empty-state">
                <p>暂无队伍记录</p>
            </div>
        `;
        return;
    }

    playerTeams.innerHTML = '';
    player.teams.forEach(team => {
        const card = document.createElement('div');
        card.className = 'team-card';

        const heroesHtml = team.members.map(m => `
            <div class="team-hero">
                <div class="team-hero-name">${m.hero_name}</div>
            </div>
        `).join('');

        const resultTag = {
            'win': '<span class="tag tag-win">胜</span>',
            'loss': '<span class="tag tag-loss">负</span>',
            'draw': '<span class="tag tag-unknown">平</span>',
            'unknown': '<span class="tag tag-unknown">未知</span>'
        }[team.battle_result] || '';

        const imageHtml = team.image_path ? `<img class="team-image" src="${API_BASE}/screenshots/${team.image_path.split('/').pop()}" alt="战报截图">` : '';

        card.innerHTML = `
            <div class="team-header">
                <div>${resultTag}</div>
                <span style="font-size: 12px; color: var(--text-secondary);">${formatDate(team.created_at)}</span>
            </div>
            <div class="team-heroes">${heroesHtml}</div>
            <div class="team-meta">
                <span>敌方位置: ${team.enemy_side || '未知'}</span>
                ${team.team_name ? `<span>队伍名: ${team.team_name}</span>` : ''}
            </div>
            ${team.notes ? `<div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">备注: ${team.notes}</div>` : ''}
            ${imageHtml}
            <div class="team-actions">
                <button class="btn btn-primary" onclick="analyzeTeam(${team.id})">分析克制</button>
            </div>
        `;

        playerTeams.appendChild(card);
    });
}

// ============================================================================
// 克制分析
// ============================================================================

async function analyzeTeam(teamId) {
    const modal = document.getElementById('counter-modal');
    const resultDiv = document.getElementById('counter-result');

    try {
        const response = await fetch(`${API_BASE}/counter/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                observed_team_id: teamId
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || '分析失败');
        }

        showCounterResult(result);
        modal.classList.add('show');

    } catch (error) {
        showToast(error.message, 'error');
    }
}

function closeCounterModal() {
    document.getElementById('counter-modal').classList.remove('show');
}

function showCounterResult(result) {
    const resultDiv = document.getElementById('counter-result');

    const heroesHtml = result.enemy_team.map(h => `
        <span class="hero-tag">${h}</span>
    `).join('');

    const tagsHtml = result.enemy_tags.map(t => `
        <span class="tag" style="background: rgba(234, 67, 53, 0.1); color: #ea4335;">${t}</span>
    `).join('');

    const recommendationsHtml = result.recommendations.map(rec => `
        <div class="counter-recommendation">
            <h5>
                ${rec.type}
                <span class="counter-recommendation-score">${rec.score}分</span>
            </h5>
            <p>${rec.reason}</p>
            ${rec.suggested_heroes?.length ? `
                <div class="counter-recommendation-heroes">
                    推荐武将: ${rec.suggested_heroes.join(', ')}
                </div>
            ` : ''}
        </div>
    `).join('');

    resultDiv.innerHTML = `
        <div class="counter-section">
            <h4>敌方队伍</h4>
            <div class="counter-enemy-heroes">${heroesHtml}</div>
        </div>

        <div class="counter-section">
            <h4>队伍类型标签</h4>
            <div class="counter-tags">${tagsHtml}</div>
        </div>

        <div class="counter-section">
            <h4>克制建议</h4>
            ${recommendationsHtml}
        </div>
    `;
}

// ============================================================================
// 武将库
// ============================================================================

async function loadHeroes() {
    try {
        const response = await fetch(`${API_BASE}/heroes`);
        const data = await response.json();

        currentHeroes = data.heroes;
        renderHeroes(currentHeroes);
        updateHeroesStats(currentHeroes);

    } catch (error) {
        console.error('加载武将库失败:', error);
    }
}

function updateHeroesStats(heroes) {
    const statsEl = document.getElementById('heroes-stats');
    const total = heroes.length;
    const withSkill = heroes.filter(h => h.skill_name).length;
    const withImage = heroes.filter(h => h.skill_images && h.skill_images.length > 0).length;

    const camps = {};
    heroes.forEach(h => {
        if (h.camp) {
            camps[h.camp] = (camps[h.camp] || 0) + 1;
        }
    });

    let campStats = '';
    if (camps['魏']) campStats += `<span class="camp-stat camp-魏">魏:${camps['魏']}</span>`;
    if (camps['蜀']) campStats += `<span class="camp-stat camp-蜀">蜀:${camps['蜀']}</span>`;
    if (camps['吴']) campStats += `<span class="camp-stat camp-吴">吴:${camps['吴']}</span>`;
    if (camps['群']) campStats += `<span class="camp-stat camp-群">群:${camps['群']}</span>`;

    statsEl.innerHTML = `
        <div class="heroes-stats-content">
            <span class="stat-item">总计: <strong>${total}</strong></span>
            <span class="stat-item">有战法: <strong>${withSkill}</strong></span>
            <span class="stat-item">有截图: <strong>${withImage}</strong></span>
            <div class="camp-stats">${campStats}</div>
        </div>
    `;
}

function renderHeroes(heroes) {
    const list = document.getElementById('heroes-list');

    if (heroes.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <p>暂无武将数据</p>
            </div>
        `;
        return;
    }

    list.innerHTML = heroes.map(hero => {
        const tags = hero.tags || [];
        const tagsHtml = tags.slice(0, 4).map(t => `
            <span class="tag">${t}</span>
        `).join('');

        return `
            <div class="hero-card" onclick="showHeroDetail(${hero.id})">
                <div class="hero-card-header">
                    <span class="hero-card-name">${hero.name}</span>
                    ${hero.camp ? `<span class="hero-card-camp camp-${hero.camp}">${hero.camp}</span>` : ''}
                </div>
                <div class="hero-card-stats">
                    <span>攻: ${hero.attack || '-'}</span>
                    <span>防: ${hero.defense || '-'}</span>
                    <span>速: ${hero.speed || '-'}</span>
                    ${hero.troop_type ? `<span>${hero.troop_type}</span>` : ''}
                </div>
                <div class="hero-card-tags">${tagsHtml}</div>
                ${hero.skill_name ? `<div class="hero-card-skill"><span class="skill-label">主战法</span><span class="skill-name">${hero.skill_name}</span></div>` : ''}
            </div>
        `;
    }).join('');
}

// 显示武将详情弹窗
let currentViewHeroId = null;

function showHeroDetail(heroId) {
    const hero = currentHeroes.find(h => h.id === heroId);
    if (!hero) return;

    currentViewHeroId = heroId;

    const modal = document.getElementById('hero-detail-modal') || createHeroDetailModal();

    // 填充武将信息
    document.getElementById('detail-hero-name').textContent = hero.name;
    document.getElementById('detail-hero-camp').textContent = hero.camp || '群';
    document.getElementById('detail-hero-type').textContent = hero.troop_type || '步兵';

    // 属性
    document.getElementById('detail-attack').textContent = hero.attack || '-';
    document.getElementById('detail-defense').textContent = hero.defense || '-';
    document.getElementById('detail-speed').textContent = hero.speed || '-';

    // 标签
    const tagsContainer = document.getElementById('detail-tags');
    tagsContainer.innerHTML = (hero.tags || []).map(t => `<span class="tag">${t}</span>`).join('');

    // 战法信息
    const skillSection = document.getElementById('detail-skill-section');
    if (hero.skill_name) {
        skillSection.style.display = 'block';
        document.getElementById('detail-skill-name').textContent = hero.skill_name;
        document.getElementById('detail-skill-type').textContent = hero.skill_type || '主动';
        document.getElementById('detail-skill-rate').textContent = hero.skill_trigger_rate ? `${hero.skill_trigger_rate}%` : '-';
        document.getElementById('detail-skill-desc').textContent = hero.skill_desc || '暂无描述';
    } else {
        skillSection.style.display = 'none';
    }

    // 战法截图
    const imagesContainer = document.getElementById('detail-skill-images');
    if (hero.skill_images && hero.skill_images.length > 0) {
        imagesContainer.innerHTML = hero.skill_images.map((img, idx) => `
            <div class="skill-image-item">
                <img src="${img}" alt="战法截图 ${idx + 1}" onclick="showImageLightbox('${img}')">
            </div>
        `).join('');
        document.querySelector('.skill-images-section').style.display = 'block';
    } else {
        imagesContainer.innerHTML = '<p class="no-data">暂无战法截图</p>';
        document.querySelector('.skill-images-section').style.display = 'block';
    }

    modal.classList.add('show');
}

// 编辑当前武将
function editCurrentHero() {
    if (!currentViewHeroId) return;
    const hero = currentHeroes.find(h => h.id === currentViewHeroId);
    if (!hero) return;

    closeHeroDetailModal();
    showHeroForm(hero);
}

// 删除当前武将
async function deleteCurrentHero() {
    if (!currentViewHeroId) return;
    const hero = currentHeroes.find(h => h.id === currentViewHeroId);
    if (!hero) return;

    if (!confirm(`确定要删除武将 "${hero.name}" 吗？此操作不可恢复。`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/heroes/${currentViewHeroId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '删除失败');
        }

        closeHeroDetailModal();
        showToast(`武将 ${hero.name} 已删除`, 'success');
        loadHeroes(); // 重新加载列表
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}

function createHeroDetailModal() {
    const modal = document.createElement('div');
    modal.id = 'hero-detail-modal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3>武将详情 - <span id="detail-hero-name"></span></h3>
                <button class="modal-close" onclick="closeHeroDetailModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="detail-hero-info">
                    <div class="hero-avatar-large" id="detail-hero-avatar"></div>
                    <div class="detail-hero-meta">
                        <div class="meta-row">
                            <span class="meta-label">阵营:</span>
                            <span class="camp-tag" id="detail-hero-camp"></span>
                        </div>
                        <div class="meta-row">
                            <span class="meta-label">兵种:</span>
                            <span id="detail-hero-type"></span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>基础属性</h4>
                    <div class="attrs-grid">
                        <div class="attr-item">
                            <text class="attr-label">攻击</text>
                            <text class="attr-value attack" id="detail-attack">-</text>
                        </div>
                        <div class="attr-item">
                            <text class="attr-label">防御</text>
                            <text class="attr-value defense" id="detail-defense">-</text>
                        </div>
                        <div class="attr-item">
                            <text class="attr-label">速度</text>
                            <text class="attr-value speed" id="detail-speed">-</text>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>武将特点</h4>
                    <div id="detail-tags" class="tags-list"></div>
                </div>

                <div class="detail-section" id="detail-skill-section" style="display: none;">
                    <h4>主战法</h4>
                    <div class="skill-info">
                        <div class="skill-header">
                            <span class="skill-name" id="detail-skill-name"></span>
                            <span class="skill-type-tag" id="detail-skill-type"></span>
                            <span class="skill-rate" id="detail-skill-rate"></span>
                        </div>
                        <p class="skill-desc" id="detail-skill-desc"></p>
                    </div>
                </div>

                <div class="detail-section skill-images-section" style="display: none;">
                    <h4>战法截图</h4>
                    <div id="detail-skill-images" class="skill-images-grid"></div>
                </div>

                <div class="detail-actions">
                    <button class="btn btn-secondary" onclick="editCurrentHero()">编辑</button>
                    <button class="btn btn-danger" onclick="deleteCurrentHero()">删除</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // 点击外部关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeHeroDetailModal();
    });

    return modal;
}

function closeHeroDetailModal() {
    const modal = document.getElementById('hero-detail-modal');
    if (modal) modal.classList.remove('show');
}

// 显示武将表单（添加或编辑）
function showHeroForm(hero = null) {
    const modal = document.getElementById('hero-form-modal');
    const title = document.getElementById('hero-form-title');

    // 重置表单
    document.getElementById('hero-form').reset();
    document.getElementById('hero-form-id').value = '';

    if (hero) {
        // 编辑模式
        title.textContent = '编辑武将';
        document.getElementById('hero-form-id').value = hero.id;
        document.getElementById('hero-name').value = hero.name || '';
        document.getElementById('hero-camp').value = hero.camp || '';
        document.getElementById('hero-troop-type').value = hero.troop_type || '';
        document.getElementById('hero-attack').value = hero.attack || '';
        document.getElementById('hero-defense').value = hero.defense || '';
        document.getElementById('hero-speed').value = hero.speed || '';
        document.getElementById('hero-tags').value = (hero.tags || []).join(',');
        document.getElementById('hero-skill-name').value = hero.skill_name || '';
        document.getElementById('hero-skill-type').value = hero.skill_type || '';
        document.getElementById('hero-skill-rate').value = hero.skill_trigger_rate || '';
        document.getElementById('hero-skill-desc').value = hero.skill_desc || '';
    } else {
        // 添加模式
        title.textContent = '添加武将';
    }

    modal.classList.add('show');
}

function closeHeroForm() {
    const modal = document.getElementById('hero-form-modal');
    if (modal) modal.classList.remove('show');
}

// 提交武将表单
async function submitHeroForm(e) {
    e.preventDefault();

    const formId = document.getElementById('hero-form-id').value;
    const heroData = {
        name: document.getElementById('hero-name').value.trim(),
        camp: document.getElementById('hero-camp').value || null,
        troop_type: document.getElementById('hero-troop-type').value || null,
        attack: parseInt(document.getElementById('hero-attack').value) || null,
        defense: parseInt(document.getElementById('hero-defense').value) || null,
        speed: parseInt(document.getElementById('hero-speed').value) || null,
        tags: document.getElementById('hero-tags').value.split(',').map(t => t.trim()).filter(t => t),
        skill_name: document.getElementById('hero-skill-name').value.trim() || null,
        skill_type: document.getElementById('hero-skill-type').value || null,
        skill_trigger_rate: parseInt(document.getElementById('hero-skill-rate').value) || null,
        skill_desc: document.getElementById('hero-skill-desc').value.trim() || null
    };

    if (!heroData.name) {
        showToast('请输入武将名称', 'error');
        return;
    }

    try {
        let response;
        if (formId) {
            // 更新
            response = await fetch(`${API_BASE}/heroes/${formId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(heroData)
            });
        } else {
            // 创建
            response = await fetch(`${API_BASE}/heroes`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(heroData)
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '保存失败');
        }

        const result = await response.json();
        closeHeroForm();
        showToast(result.message, 'success');
        loadHeroes(); // 重新加载列表
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

// 图片灯箱
function showImageLightbox(src) {
    const lightbox = document.getElementById('image-lightbox') || createImageLightbox();
    document.getElementById('lightbox-img').src = src;
    lightbox.classList.add('show');
}

function createImageLightbox() {
    const lightbox = document.createElement('div');
    lightbox.id = 'image-lightbox';
    lightbox.className = 'lightbox';
    lightbox.innerHTML = `
        <span class="lightbox-close" onclick="closeLightbox()">&times;</span>
        <img id="lightbox-img" src="" alt="">
    `;
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) closeLightbox();
    });
    document.body.appendChild(lightbox);
    return lightbox;
}

function closeLightbox() {
    const lightbox = document.getElementById('image-lightbox');
    if (lightbox) lightbox.classList.remove('show');
}

function initHeroSearch() {
    const input = document.getElementById('hero-search-input');
    const campFilter = document.getElementById('hero-camp-filter');
    const skillFilter = document.getElementById('hero-skill-filter');

    const filterHeroes = () => {
        const query = input.value.trim().toLowerCase();
        const camp = campFilter.value;
        const skillType = skillFilter.value;

        let filtered = [...currentHeroes];

        // 搜索过滤
        if (query) {
            filtered = filtered.filter(h =>
                h.name.toLowerCase().includes(query) ||
                (h.camp && h.camp.toLowerCase().includes(query)) ||
                (h.skill_name && h.skill_name.toLowerCase().includes(query)) ||
                (h.tags && h.tags.some(t => t.toLowerCase().includes(query)))
            );
        }

        // 阵营过滤
        if (camp) {
            filtered = filtered.filter(h => h.camp === camp);
        }

        // 战法过滤
        if (skillType === 'has-skill') {
            filtered = filtered.filter(h => h.skill_name);
        } else if (skillType === 'has-image') {
            filtered = filtered.filter(h => h.skill_images && h.skill_images.length > 0);
        }

        renderHeroes(filtered);
        updateHeroesStats(filtered);
    };

    input.addEventListener('input', filterHeroes);
    campFilter.addEventListener('change', filterHeroes);
    skillFilter.addEventListener('change', filterHeroes);
}

// ============================================================================
// 初始化
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // 导航按钮
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const page = btn.dataset.page;
            showPage(page);
        });
    });

    // 搜索按钮
    document.getElementById('btn-search').addEventListener('click', searchPlayers);
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchPlayers();
    });

    // 赛季输入变化
    document.getElementById('season-input').addEventListener('input', updateUploadUI);

    // 初始化各模块
    initUpload();
    initConfirm();
    initHeroSearch();
    initAllPlayersDropdown();
    initTeamsPage();

    // 武将表单提交
    document.getElementById('hero-form').addEventListener('submit', submitHeroForm);
    // 队伍表单提交
    document.getElementById('team-form').addEventListener('submit', submitTeamForm);

    console.log('率土战报情报库已初始化');
});

// ============================================================================
// 玩家队伍管理
// ============================================================================

let currentTeams = [];

function initTeamsPage() {
    const searchInput = document.getElementById('team-search-input');
    const refreshBtn = document.getElementById('btn-refresh-teams');

    searchInput.addEventListener('input', filterTeams);
    refreshBtn.addEventListener('click', loadTeams);
}

async function loadTeams() {
    try {
        const response = await fetch(`${API_BASE}/player-teams`);
        const data = await response.json();

        currentTeams = data.teams || [];
        renderTeams(currentTeams);
        updateTeamsStats(currentTeams);

    } catch (error) {
        console.error('加载队伍列表失败:', error);
        showToast('加载队伍列表失败', 'error');
    }
}

function updateTeamsStats(teams) {
    const statsEl = document.getElementById('teams-stats');
    const total = teams.length;

    // 按玩家分组统计
    const playerCount = new Set(teams.map(t => t.player_id)).size;

    statsEl.innerHTML = `
        <div class="teams-stats-content">
            <span class="stat-item">总计: <strong>${total}</strong></span>
            <span class="stat-item">玩家数: <strong>${playerCount}</strong></span>
        </div>
    `;
}

function filterTeams() {
    const query = document.getElementById('team-search-input').value.trim().toLowerCase();

    if (!query) {
        renderTeams(currentTeams);
        return;
    }

    const filtered = currentTeams.filter(team =>
        team.player_id.toLowerCase().includes(query) ||
        team.team_name.toLowerCase().includes(query)
    );

    renderTeams(filtered);
}

function renderTeams(teams) {
    const list = document.getElementById('teams-list');

    if (teams.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <p>暂无队伍数据</p>
                <p style="margin-top: 8px; font-size: 12px;">点击右上角"添加队伍"开始创建</p>
            </div>
        `;
        return;
    }

    list.innerHTML = teams.map(team => {
        const heroes = team.hero_lineup || [];
        const heroesHtml = heroes.length > 0
            ? heroes.map(h => `<span class="hero-tag">${h}</span>`).join('')
            : '<span style="color: var(--text-secondary); font-size: 12px;">暂无武将</span>';

        return `
            <div class="team-card" onclick="showTeamDetail(${team.id})">
                <div class="team-card-header">
                    <span class="team-card-name">${team.team_name}</span>
                    <span class="team-card-level">Lv.${team.level}</span>
                </div>
                <div class="team-card-player">
                    <span class="player-id-label">玩家ID:</span>
                    <span class="player-id-value">${team.player_id}</span>
                </div>
                <div class="team-card-heroes">${heroesHtml}</div>
                <div class="team-card-footer">
                    <span class="team-date">${formatDate(team.updated_at)}</span>
                </div>
            </div>
        `;
    }).join('');
}

function showTeamForm(team = null) {
    const modal = document.getElementById('team-form-modal');
    const title = document.getElementById('team-form-title');

    // 重置表单
    document.getElementById('team-form').reset();
    document.getElementById('team-form-id').value = '';

    if (team) {
        // 编辑模式
        title.textContent = '编辑队伍';
        document.getElementById('team-form-id').value = team.id;
        document.getElementById('team-player-id').value = team.player_id || '';
        document.getElementById('team-name').value = team.team_name || '';
        document.getElementById('team-heroes').value = (team.hero_lineup || []).join(',');
        document.getElementById('team-level').value = team.level || 1;
        document.getElementById('team-notes').value = team.notes || '';
    } else {
        // 添加模式
        title.textContent = '添加队伍';
    }

    modal.classList.add('show');
}

function closeTeamForm() {
    const modal = document.getElementById('team-form-modal');
    if (modal) modal.classList.remove('show');
}

async function submitTeamForm(e) {
    e.preventDefault();

    const formId = document.getElementById('team-form-id').value;
    const heroLineup = document.getElementById('team-heroes').value
        .split(',')
        .map(h => h.trim())
        .filter(h => h);

    const teamData = {
        player_id: document.getElementById('team-player-id').value.trim(),
        team_name: document.getElementById('team-name').value.trim(),
        hero_lineup: heroLineup,
        level: parseInt(document.getElementById('team-level').value) || 1,
        notes: document.getElementById('team-notes').value.trim() || null
    };

    if (!teamData.player_id || !teamData.team_name) {
        showToast('请填写玩家ID和队伍名称', 'error');
        return;
    }

    try {
        let response;
        if (formId) {
            // 更新
            response = await fetch(`${API_BASE}/player-teams/${formId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(teamData)
            });
        } else {
            // 创建
            response = await fetch(`${API_BASE}/player-teams`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(teamData)
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '保存失败');
        }

        const result = await response.json();
        closeTeamForm();
        showToast(result.message, 'success');
        loadTeams(); // 重新加载列表
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

function showTeamDetail(teamId) {
    const team = currentTeams.find(t => t.id === teamId);
    if (!team) return;

    const modal = document.getElementById('team-detail-modal');
    const title = document.getElementById('team-detail-title');
    const content = document.getElementById('team-detail-content');

    title.textContent = team.team_name;

    const heroes = team.hero_lineup || [];
    const heroesHtml = heroes.length > 0
        ? heroes.map(h => `<span class="hero-tag">${h}</span>`).join('')
        : '<p class="no-data">暂无武将</p>';

    content.innerHTML = `
        <div class="team-detail-section">
            <div class="detail-row">
                <label>玩家ID:</label>
                <span>${team.player_id}</span>
            </div>
            <div class="detail-row">
                <label>等级:</label>
                <span>Lv.${team.level || 1}</span>
            </div>
            <div class="detail-row">
                <label>创建时间:</label>
                <span>${formatDate(team.created_at)}</span>
            </div>
            <div class="detail-row">
                <label>更新时间:</label>
                <span>${formatDate(team.updated_at)}</span>
            </div>
        </div>

        <div class="team-detail-section">
            <h4>武将阵容</h4>
            <div class="heroes-tags">${heroesHtml}</div>
        </div>

        ${team.notes ? `
            <div class="team-detail-section">
                <h4>备注</h4>
                <p class="team-notes">${team.notes}</p>
            </div>
        ` : ''}

        <div class="detail-actions">
            <button class="btn btn-secondary" onclick="editTeam(${team.id})">编辑</button>
            <button class="btn btn-danger" onclick="deleteTeam(${team.id})">删除</button>
        </div>
    `;

    modal.classList.add('show');
}

function closeTeamDetail() {
    const modal = document.getElementById('team-detail-modal');
    if (modal) modal.classList.remove('show');
}

function editTeam(teamId) {
    const team = currentTeams.find(t => t.id === teamId);
    if (!team) return;

    closeTeamDetail();
    showTeamForm(team);
}

async function deleteTeam(teamId) {
    const team = currentTeams.find(t => t.id === teamId);
    if (!team) return;

    if (!confirm(`确定要删除队伍 "${team.team_name}" 吗？此操作不可恢复。`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/player-teams/${teamId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '删除失败');
        }

        closeTeamDetail();
        showToast(`队伍 "${team.team_name}" 已删除`, 'success');
        loadTeams(); // 重新加载列表
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}
