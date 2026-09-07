const API_BASE = 'http://localhost:8765/api/v1';

let presets = [];
let tools = [];
let activeWorkflows = [];
let selectedWorkflowId = null;
let refreshInterval = null;
let currentPresetToStart = null;

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadPresets();
    loadTools();
    startAutoRefresh();
});

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            switchPage(page);
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function switchPage(pageName) {
    const pages = document.querySelectorAll('.page');
    pages.forEach(p => p.classList.add('hidden'));

    const targetPage = document.getElementById(`page-${pageName}`);
    if (targetPage) {
        targetPage.classList.remove('hidden');
    }

    const titles = {
        'v4': 'V4 智能编排',
        'workflows': '工作流管理',
        'monitor': '工作流监控',
        'tools': '工具管理',
        'history': '历史记录'
    };
    document.getElementById('page-title').textContent = titles[pageName] || '工作流管理';

    if (pageName === 'monitor') {
        loadActiveWorkflows();
    }
}

function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        if (!document.getElementById('page-monitor').classList.contains('hidden')) {
            loadActiveWorkflows();
            if (selectedWorkflowId) {
                loadWorkflowDetail(selectedWorkflowId);
            }
        }
    }, 2000);
}

function refreshData() {
    loadPresets();
    loadTools();
    loadActiveWorkflows();
    showToast('刷新成功', '数据已更新', '✅');
}

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '请求失败');
        }
        return await response.json();
    } catch (error) {
        console.error('API请求失败:', error);
        updateStatusIndicator(false);
        throw error;
    }
}

function updateStatusIndicator(online) {
    const dot = document.querySelector('.status-dot');
    const text = document.querySelector('.status-indicator span');
    if (online) {
        dot.classList.add('online');
        text.textContent = 'API 在线';
    } else {
        dot.classList.remove('online');
        text.textContent = 'API 离线';
    }
}

// ==================== 工作流管理 ====================

async function loadPresets() {
    try {
        presets = await fetchAPI('/presets');
        renderPresets(presets);
        updateStatusIndicator(true);
    } catch (error) {
        console.error('加载预设失败:', error);
    }
}

function renderPresets(filteredPresets) {
    const grid = document.getElementById('presets-grid');
    grid.innerHTML = '';
    
    if (filteredPresets.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-icon">📭</div>
                <p>未找到匹配的工作流预设</p>
            </div>
        `;
        return;
    }
    
    filteredPresets.forEach(preset => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="card-header">
                <h3 class="card-title">${preset.name}</h3>
                <span class="card-category">${preset.category || '未分类'}</span>
            </div>
            <p class="card-description">${preset.description}</p>
            <div class="card-meta">
                <div class="meta-item">
                    <span class="meta-icon">📋</span>
                    <span>${preset.steps_count} 步骤</span>
                </div>
            </div>
            <div class="card-tags">
                ${preset.tags?.map(tag => `<span class="tag">${tag}</span>`).join('') || ''}
            </div>
            <div class="card-actions">
                <button class="btn btn-primary" onclick="openStartModal('${preset.id}', '${preset.name}')">启动</button>
            </div>
        `;
        grid.appendChild(card);
    });
}

function filterPresets() {
    const search = document.getElementById('preset-search').value.toLowerCase();
    const category = document.getElementById('category-filter').value;
    
    let filtered = presets;
    
    if (search) {
        filtered = filtered.filter(p => 
            p.name.toLowerCase().includes(search) ||
            p.description.toLowerCase().includes(search)
        );
    }
    
    if (category) {
        filtered = filtered.filter(p => p.category === category);
    }
    
    renderPresets(filtered);
}

function openStartModal(presetId, presetName) {
    currentPresetToStart = presetId;
    document.getElementById('start-preset-name').value = presetName;
    document.getElementById('start-input-file').value = '';
    document.getElementById('modal-start').classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
    currentPresetToStart = null;
}

async function startWorkflow() {
    if (!currentPresetToStart) return;
    
    const inputFile = document.getElementById('start-input-file').value;
    const mode = document.getElementById('start-mode').value;
    const workers = parseInt(document.getElementById('start-workers').value);
    
    const inputParams = {};
    if (inputFile) {
        inputParams.input_file = inputFile;
    }
    
    try {
        const response = await fetchAPI('/workflow/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                preset_id: currentPresetToStart,
                input_params: Object.keys(inputParams).length > 0 ? inputParams : null,
                mode: mode,
                max_workers: workers
            })
        });
        
        closeModal('modal-start');
        showToast('工作流已启动', `ID: ${response.workflow_id}`, '✅');
        
        setTimeout(() => {
            switchPage('monitor');
            loadActiveWorkflows();
        }, 500);
    } catch (error) {
        showToast('启动失败', error.message, '❌');
    }
}

// ==================== 监控 ====================

async function loadActiveWorkflows() {
    try {
        activeWorkflows = await fetchAPI('/workflows/active');
        renderActiveWorkflows();
    } catch (error) {
        console.error('加载活跃工作流失败:', error);
    }
}

function renderActiveWorkflows() {
    const list = document.getElementById('active-workflows-list');
    const empty = document.getElementById('empty-active');
    
    list.innerHTML = '';
    
    if (activeWorkflows.length === 0) {
        empty.classList.remove('hidden');
        return;
    }
    
    empty.classList.add('hidden');
    
    activeWorkflows.forEach(wf => {
        const item = document.createElement('div');
        item.className = `workflow-item ${selectedWorkflowId === wf.workflow_id ? 'active' : ''}`;
        item.onclick = () => selectWorkflow(wf.workflow_id);
        
        const statusClass = getStatusClass(wf.status);
        
        item.innerHTML = `
            <div class="workflow-item-header">
                <span class="workflow-item-title">${wf.workflow_name}</span>
                <span class="workflow-item-id">${wf.workflow_id}</span>
            </div>
            <div class="workflow-item-status ${statusClass}">${getStatusText(wf.status)}</div>
            <div class="workflow-item-meta">
                <span>${wf.steps_completed} 步骤完成</span>
                ${wf.paused ? '<span>⏸️ 已暂停</span>' : ''}
            </div>
        `;
        list.appendChild(item);
    });
}

function selectWorkflow(wfId) {
    selectedWorkflowId = wfId;
    loadActiveWorkflows();
    loadWorkflowDetail(wfId);
}

async function loadWorkflowDetail(wfId) {
    try {
        const detail = await fetchAPI(`/workflow/${wfId}`);
        renderWorkflowDetail(detail);
    } catch (error) {
        console.error('加载工作流详情失败:', error);
    }
}

function renderWorkflowDetail(detail) {
    const empty = document.getElementById('detail-empty');
    const content = document.getElementById('detail-content');
    
    empty.classList.add('hidden');
    content.classList.remove('hidden');
    
    document.getElementById('detail-name').textContent = detail.workflow_name;
    document.getElementById('detail-id').textContent = detail.workflow_id;
    document.getElementById('detail-id').className = 'badge badge-id';
    
    const statusBadge = document.getElementById('detail-status');
    statusBadge.textContent = getStatusText(detail.status);
    statusBadge.className = `badge badge-status-${detail.status}`;
    
    // 进度条
    const total = detail.total_steps || 1;
    const completed = detail.completed_steps || 0;
    const progress = total > 0 ? (completed / total) * 100 : 0;
    document.getElementById('progress-fill').style.width = `${progress}%`;
    document.getElementById('progress-text').textContent = `${Math.round(progress)}%`;
    document.getElementById('progress-time').textContent = `${(detail.total_duration_ms / 1000).toFixed(1)}s`;
    
    // 步骤列表
    const stepsList = document.getElementById('steps-list');
    stepsList.innerHTML = '';
    
    detail.steps.forEach(step => {
        const stepItem = document.createElement('div');
        stepItem.className = `step-item ${step.status}`;
        
        const icon = getStepIcon(step.status);
        const statusText = getStatusText(step.status);
        
        stepItem.innerHTML = `
            <span class="step-icon">${icon}</span>
            <div class="step-info">
                <div class="step-name">${step.name}</div>
                <div class="step-tool">${step.tool} / ${step.operation}</div>
            </div>
            <span class="step-status ${getStepStatusClass(step.status)}">${statusText}</span>
            <span class="step-duration">${(step.duration_ms / 1000).toFixed(1)}s</span>
        `;
        stepsList.appendChild(stepItem);
    });
    
    // 输出文件
    const outputFiles = document.getElementById('output-files');
    outputFiles.innerHTML = '';
    
    if (detail.output_files && detail.output_files.length > 0) {
        detail.output_files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'output-file';
            fileItem.innerHTML = `
                <span class="output-file-icon">📄</span>
                <span>${file}</span>
            `;
            outputFiles.appendChild(fileItem);
        });
    } else {
        outputFiles.innerHTML = '<div style="color: #64748b; padding: 10px;">暂无输出文件</div>';
    }
    
    // 链接
    document.getElementById('link-log').href = detail.log_file_path ? `file:///${detail.log_file_path.replace(/\\/g, '/')}` : '#';
    document.getElementById('link-report').href = detail.report_file_path ? `file:///${detail.report_file_path.replace(/\\/g, '/')}` : '#';
    document.getElementById('link-checkpoint').href = detail.checkpoint_path ? `file:///${detail.checkpoint_path.replace(/\\/g, '/')}` : '#';
    
    // 控制按钮状态
    const isRunning = detail.status === 'running';
    const isPaused = detail.paused;
    
    document.getElementById('action-pause').style.display = isRunning && !isPaused ? 'block' : 'none';
    document.getElementById('action-resume').style.display = isPaused ? 'block' : 'none';
    document.getElementById('action-cancel').style.display = isRunning ? 'block' : 'none';
}

async function controlWorkflow(action) {
    if (!selectedWorkflowId) return;
    
    try {
        await fetchAPI(`/workflow/${selectedWorkflowId}/${action}`, {
            method: 'POST'
        });
        
        const actionNames = {
            'pause': '暂停',
            'resume': '恢复',
            'cancel': '取消'
        };
        
        showToast(`${actionNames[action]}请求已发送`, '操作已执行', '✅');
        
        setTimeout(() => {
            loadActiveWorkflows();
            loadWorkflowDetail(selectedWorkflowId);
        }, 500);
    } catch (error) {
        showToast('操作失败', error.message, '❌');
    }
}

// ==================== 工具管理 ====================

async function loadTools() {
    try {
        tools = await fetchAPI('/tools');
        renderTools();
    } catch (error) {
        console.error('加载工具失败:', error);
    }
}

function renderTools() {
    const grid = document.querySelector('.tools-grid');
    grid.innerHTML = '';
    
    const toolIcons = {
        'ffmpeg': '🎬',
        'topaz': '✨',
        'blender': '3️⃣',
        'after_effects': '🎨',
        'premiere_pro': '📹',
        'photoshop': '🖼️',
        'illustrator': '✏️',
        'media_encoder': '🔄',
        'audition': '🔊'
    };
    
    const toolNames = {
        'ffmpeg': 'FFmpeg',
        'topaz': 'Topaz Video AI',
        'blender': 'Blender',
        'after_effects': 'Adobe After Effects',
        'premiere_pro': 'Adobe Premiere Pro',
        'photoshop': 'Adobe Photoshop',
        'illustrator': 'Adobe Illustrator',
        'media_encoder': 'Adobe Media Encoder',
        'audition': 'Adobe Audition'
    };
    
    Object.entries(tools).forEach(([name, info]) => {
        const card = document.createElement('div');
        card.className = 'tool-card';
        
        const icon = toolIcons[name] || '🛠️';
        const displayName = toolNames[name] || name;
        const isAvailable = info.available;
        
        card.innerHTML = `
            <div class="tool-header">
                <div class="tool-icon">${icon}</div>
                <div class="tool-info">
                    <h3>${displayName}</h3>
                    <div class="tool-status ${isAvailable ? 'available' : 'unavailable'}">
                        ${isAvailable ? '✓ 可用' : '✗ 不可用'}
                    </div>
                </div>
            </div>
            <div class="tool-stats">
                <div class="tool-stat">
                    <div class="tool-stat-value">${info.operations_count}</div>
                    <div class="tool-stat-label">操作数</div>
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

// ==================== 历史记录 ====================
// 历史记录需要后端支持，这里先显示模拟数据

// ==================== 工具函数 ====================

function getStatusClass(status) {
    const classes = {
        'running': 'status-running',
        'success': 'status-success',
        'error': 'status-error',
        'skipped': 'status-paused'
    };
    return classes[status] || 'status-running';
}

function getStatusText(status) {
    const texts = {
        'running': '运行中',
        'success': '成功',
        'error': '失败',
        'skipped': '已跳过',
        'pending': '等待中'
    };
    return texts[status] || status;
}

function getStepIcon(status) {
    const icons = {
        'running': '🔄',
        'success': '✅',
        'error': '❌',
        'skipped': '⏭️',
        'pending': '⏳'
    };
    return icons[status] || '📋';
}

function getStepStatusClass(status) {
    const classes = {
        'running': 'status-running',
        'success': 'status-success',
        'error': 'status-error',
        'skipped': 'status-paused'
    };
    return classes[status] || '';
}

function showToast(title, message, icon = '✅') {
    const toast = document.getElementById('toast');
    document.getElementById('toast-icon').textContent = icon;
    document.getElementById('toast-title').textContent = title;
    document.getElementById('toast-message').textContent = message;
    
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// ==================== V4 智能编排 ====================

async function runV4Orchestrate() {
    const request = document.getElementById('v4-request').value.trim();
    if (!request) {
        showToast('请输入需求', '请描述你需要完成的工作', '⚠️');
        return;
    }

    const model = document.getElementById('v4-model').value;
    const mode = document.getElementById('v4-mode').value;
    const dryRun = document.getElementById('v4-dry-run').checked;

    // 显示状态
    document.getElementById('v4-status').classList.remove('hidden');
    document.getElementById('v4-result').classList.add('hidden');
    document.getElementById('v4-error').classList.add('hidden');
    document.getElementById('v4-run-btn').disabled = true;

    const statusText = dryRun ? 'V4 分析中（预览模式）...' : 'V4 分析并执行中...';
    document.getElementById('v4-status-text').textContent = statusText;

    try {
        const response = await fetch(`${API_BASE}/v4/orchestrate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                request: request,
                model: model,
                dry_run: dryRun,
                mode: mode,
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '请求失败');
        }

        const data = await response.json();
        renderV4Result(data);
    } catch (error) {
        document.getElementById('v4-status').classList.add('hidden');
        document.getElementById('v4-error').classList.remove('hidden');
        document.getElementById('v4-error-message').textContent = error.message;
    } finally {
        document.getElementById('v4-run-btn').disabled = false;
    }
}

function renderV4Result(data) {
    document.getElementById('v4-status').classList.add('hidden');

    if (!data.success) {
        document.getElementById('v4-error').classList.remove('hidden');
        document.getElementById('v4-error-message').textContent =
            data.error || 'V4 未能生成有效工作流';
        return;
    }

    const resultDiv = document.getElementById('v4-result');
    resultDiv.classList.remove('hidden');

    const wf = data.workflow || {};
    document.getElementById('v4-workflow-name').textContent =
        wf.name || 'V4 自定义工作流';
    document.getElementById('v4-workflow-desc').textContent =
        wf.description || '';

    // 渲染步骤
    const stepsList = document.getElementById('v4-steps-list');
    stepsList.innerHTML = '';

    const steps = wf.steps || [];
    steps.forEach((step, i) => {
        const stepDiv = document.createElement('div');
        stepDiv.className = 'v4-step-item';

        const deps = step.depends_on || [];
        const depStr = deps.length > 0
            ? ` <span class="v4-dep">(依赖: ${deps.join(', ')})</span>` : '';

        stepDiv.innerHTML = `
            <div class="v4-step-num">${i + 1}</div>
            <div class="v4-step-body">
                <div class="v4-step-title">
                    <span class="v4-step-tool">${step.tool}</span>
                    <span class="v4-step-op">${step.operation}</span>
                    ${depStr}
                </div>
                <div class="v4-step-name">${step.name || ''}</div>
                <div class="v4-step-params">${
                    JSON.stringify(step.params || {}, null, 2)
                        .replace(/"/g, '').replace(/[{}]/g, '')
                        .substring(0, 200)
                }</div>
            </div>
        `;
        stepsList.appendChild(stepDiv);
    });

    // 执行结果
    const execResult = document.getElementById('v4-execution-result');
    if (data.dry_run) {
        execResult.classList.add('hidden');
        showToast('预览完成', `生成 ${steps.length} 个步骤`, '✅');
    } else {
        execResult.classList.remove('hidden');
        const summary = data.summary || {};
        const stats = document.getElementById('v4-stats');
        stats.innerHTML = `
            <div class="v4-stat">
                <div class="v4-stat-value v4-stat-success">${summary.successful || 0}</div>
                <div class="v4-stat-label">成功</div>
            </div>
            <div class="v4-stat">
                <div class="v4-stat-value v4-stat-error">${summary.failed || 0}</div>
                <div class="v4-stat-label">失败</div>
            </div>
            <div class="v4-stat">
                <div class="v4-stat-value">${summary.total_steps || 0}</div>
                <div class="v4-stat-label">总步骤</div>
            </div>
            <div class="v4-stat">
                <div class="v4-stat-value">${((summary.duration_ms || 0) / 1000).toFixed(1)}s</div>
                <div class="v4-stat-label">耗时</div>
            </div>
        `;

        const outputFiles = document.getElementById('v4-output-files');
        const files = summary.output_files || [];
        if (files.length > 0) {
            outputFiles.innerHTML = '<h5>输出文件</h5>' +
                files.map(f => `<div class="v4-output-file">📄 ${f}</div>`).join('');
        } else {
            outputFiles.innerHTML = '';
        }

        const icon = summary.failed > 0 ? '⚠️' : '✅';
        const msg = summary.failed > 0
            ? `${summary.failed} 个步骤失败` : '全部步骤成功';
        showToast('执行完成', msg, icon);
    }
}
