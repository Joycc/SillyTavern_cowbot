import { extension_settings, getContext } from "../../../extensions.js";
import { saveSettingsDebounced } from "../../../../script.js";

const extensionName = "st_extension_wechat_bridge";

const defaultSettings = {
    pythonBase: "http://127.0.0.1:8080/api",
    queueApi: "http://127.0.0.1:8080/api/queue",
    queueIntervalMs: 2000,
    qrIntervalMs: 3000,
    autoConnect: false,
    boundCharacter: "",
};

extension_settings[extensionName] = {
    ...defaultSettings,
    ...(extension_settings[extensionName] || {}),
};

let $statusText = null;
let $qrImg = null;
let $characterSelect = null;
let $connectBtn = null;
let $autoConnectCheckbox = null;

let qrTimer = null;
let queueTimer = null;
let lastWechatUserId = null;

function updateDebugLog(message) {
    const debugLog = $('#debug_log');
    const timestamp = new Date().toLocaleTimeString();
    const line = `[${timestamp}] ${message}`;

    if (debugLog.length > 0) {
        const currentContent = debugLog.val() || '';
        debugLog.val(`${currentContent}${line}\n`);
        debugLog.scrollTop(debugLog[0].scrollHeight);
    }
    console.log(`[${extensionName}] ${message}`);
}

function setStatus(text, connected = null) {
    if ($statusText?.length) {
        $statusText.text(text);
        if (connected === true) {
            $statusText.css('color', '#00ff00');
        } else if (connected === false) {
            $statusText.css('color', '#ffcc00');
        } else {
            $statusText.css('color', '');
        }
    }
    updateDebugLog(text);
}

function updateConnectionButtons(connected) {
    if ($connectBtn?.length) {
        $connectBtn.prop('disabled', connected);
    }
}

function cacheElements() {
    $statusText = $('#wechat_status_text');
    $qrImg = $('#wechat_qr_img');
    $characterSelect = $('#wechat_character_select');
    $connectBtn = $('#wechat_connect_btn');
    $autoConnectCheckbox = $('#ws_auto_connect');
}

function getCharactersArray() {
    const context = getContext();
    if (context && Array.isArray(context.characters)) {
        return context.characters;
    }
    if (Array.isArray(window.characters)) {
        return window.characters;
    }
    return [];
}

function getCurrentActiveCharacterName() {
    const context = getContext();
    const chars = getCharactersArray();
    const candidateId = Number(context?.characterId ?? window.this_chid);

    if (Number.isInteger(candidateId) && candidateId >= 0 && chars[candidateId]) {
        return String(chars[candidateId]?.name || '');
    }
    return '';
}

function initCharacterSelect() {
    if (!$characterSelect) return;
    
    const chars = getCharactersArray();
    const currentVal = String($characterSelect.val() || extension_settings[extensionName].boundCharacter || '');
    
    $characterSelect.empty();

    chars.forEach((char, index) => {
        const name = char?.name ? String(char.name) : `角色${index + 1}`;
        $characterSelect.append(`<option value="${name}">${name}</option>`);
    });

    if (chars.length === 0) {
        $characterSelect.append('<option value="">无可用角色</option>');
    } else if (currentVal && chars.some(char => String(char?.name || '') === currentVal)) {
        $characterSelect.val(currentVal);
    } else {
        const firstVal = $characterSelect.find('option:first').val();
        $characterSelect.val(firstVal);
        extension_settings[extensionName].boundCharacter = firstVal;
    }
}

function isSelectedCharacterActive() {
    const selectedName = String($characterSelect.val() || '');
    if (!selectedName) return false;

    const activeName = getCurrentActiveCharacterName();
    if (!activeName) return true;

    return activeName === selectedName;
}

function stopQrPolling() {
    if (qrTimer) {
        clearInterval(qrTimer);
        qrTimer = null;
    }
}

function stopQueuePolling() {
    if (queueTimer) {
        clearInterval(queueTimer);
        queueTimer = null;
    }
}

function startQueuePolling() {
    stopQueuePolling();
    const interval = Number(extension_settings[extensionName].queueIntervalMs) || 2000;
    queueTimer = setInterval(pollQueue, interval);
    pollQueue();
}

function startQrPolling() {
    stopQrPolling();
    const interval = Number(extension_settings[extensionName].qrIntervalMs) || 3000;
    qrTimer = setInterval(pollQrCode, interval);
    pollQrCode();
}

// ==========================================
// 【终极修复 1】：更稳健的消息注入与发送触发
// ==========================================
function injectMessageToSt(content) {
    const $textarea = $('#send_textarea');
    $textarea.val(content);
    
    // 强制触发 input 事件，让酒馆底层感知到字数变化
    $textarea[0].dispatchEvent(new Event('input', { bubbles: true }));
    
    // 延迟 150 毫秒点击发送按钮，等待 React/Vue 状态更新完成
    setTimeout(() => {
        $('#send_but').trigger('click');
        setStatus(`已触发 AI 回复，等待生成...`, true);
    }, 150);
}

function extractReplyText(mesObj) {
    // 兼容字符串和对象两种提取方式
    const raw = mesObj?.message?.mes || mesObj?.mes || mesObj?.text || mesObj?.message || (typeof mesObj === 'string' ? mesObj : '');
    return String(raw).replace(/\*.*?\*/g, '').replace(/\n{3,}/g, '\n\n').trim();
}

async function pollQrCode() {
    const { pythonBase } = extension_settings[extensionName];

    try {
        const resp = await fetch(`${pythonBase}/qrcode`, { method: 'GET' });
        if (!resp.ok) return;

        const data = await resp.json();
        const rawStatus = String(data?.status || '').toUpperCase();
        const qrData = data?.qr_data || data?.base64;

        if (typeof qrData === 'string' && /^https?:\/\//i.test(qrData)) {
            $('#wechat_qr_container').show();
            $('#wechat_qr_img').hide();
            $('#wechat_qr_link_box').show();
            $('#wechat_qr_link').attr('href', qrData);
        }

        if (rawStatus.includes('LOGGED_IN')) {
            stopQrPolling();
            $('#wechat_qr_container').hide();
            setStatus('微信已登录，开始监听消息', true);
            updateConnectionButtons(true);
            startQueuePolling();
        } else if (rawStatus.includes('SCAN') || rawStatus.includes('CONFIRM')) {
            setStatus('已扫码，请在手机端点击确认登录...', false);
        } else if (rawStatus.includes('WAIT')) {
            setStatus('请点击下方链接获取二维码并扫码...', false);
        }
    } catch (error) {
        setStatus(`二维码轮询异常... ${error?.message || ''}`, false);
    }
}

async function pollQueue() {
    const realQueueApi = `${extension_settings[extensionName].pythonBase}/queue`;

    try {
        const resp = await fetch(realQueueApi, { method: 'GET' });
        if (!resp.ok) return;

        const queue = await resp.json();
        if (!Array.isArray(queue) || queue.length === 0) return;

        for (const item of queue) {
            const userId = item?.user_id;
            const content = item?.content;
            if (!userId || !content) continue;

            lastWechatUserId = String(userId);

            if (!isSelectedCharacterActive()) {
                setStatus('收到微信消息，但当前聊天角色与绑定角色不一致，已跳过。');
                continue;
            }

            setStatus(`接收微信消息：${content.substring(0, 10)}...`, true);
            injectMessageToSt(String(content));
        }
    } catch (error) {
        setStatus(`消息轮询失败，等待重试... ${error?.message || ''}`, false);
    }
}

async function sendReplyToWechat(text) {
    if (!lastWechatUserId || !text) return;
    const { pythonBase } = extension_settings[extensionName];

    try {
        setStatus(`正在回传给微信...`);
        const resp = await fetch(`${pythonBase}/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: lastWechatUserId, content: text }),
        });

        if (!resp.ok) {
            setStatus(`回传微信失败，HTTP ${resp.status}`, false);
        } else {
            setStatus(`✅ 回传微信成功！`, true);
        }
    } catch (error) {
        setStatus(`回传微信异常... ${error?.message || ''}`, false);
    }
}

function bindEvents() {
    $connectBtn.on('click', () => {
        setStatus('正在获取二维码链接...');
        startQrPolling();
    });

    $characterSelect.on('mouseenter focus click', () => {
        initCharacterSelect();
    });

    $characterSelect.on('change', function () {
        extension_settings[extensionName].boundCharacter = String($(this).val() || '');
        saveSettingsDebounced();
        setStatus(`已绑定角色：${extension_settings[extensionName].boundCharacter || '未选择'}`);
    });

    if ($autoConnectCheckbox?.length) {
        $autoConnectCheckbox.prop('checked', !!extension_settings[extensionName].autoConnect);
        $autoConnectCheckbox.on('change', function () {
            const checked = !!$(this).prop('checked');
            extension_settings[extensionName].autoConnect = checked;
            saveSettingsDebounced();
            setStatus(checked ? '已启用自动连接' : '已禁用自动连接');
            if (checked) {
                startQrPolling();
            }
        });
    }

    // ==========================================
    // 【终极修复 2】：监听新旧所有可能的完成事件
    // ==========================================
    if (window.eventSource && typeof window.eventSource.on === 'function') {
        window.eventSource.on('charactersLoaded', () => {
            initCharacterSelect();
        });
        
        // 兼容旧版本酒馆
        window.eventSource.on('characterMessageRendered', async (eventData) => {
            const cleanText = extractReplyText(eventData);
            if (!cleanText) return;
            await sendReplyToWechat(cleanText);
        });

        // 兼容最新版酒馆：生成结束时，精准抓取最后一条消息
        window.eventSource.on('generation_ended', async () => {
            const context = getContext();
            if (!context || !Array.isArray(context.chat) || context.chat.length === 0) return;
            
            // 获取聊天界面的最后一条记录
            const lastMessage = context.chat[context.chat.length - 1];
            
            // 确保最后一条是 AI 发的，而不是用户的自言自语
            if (lastMessage.is_user) return;

            const cleanText = extractReplyText(lastMessage);
            if (!cleanText) return;

            // 避免两个事件同时触发导致发送两遍
            if (window._lastSentWechatMsg === cleanText) return;
            window._lastSentWechatMsg = cleanText;

            await sendReplyToWechat(cleanText);
        });
    }

    window.addEventListener('beforeunload', () => {
        stopQrPolling();
        stopQueuePolling();
    });
}

async function appendSettingsHtml() {
    if ($('#wechat_bridge_panel').length > 0) return;

    const inlineHtml = `
        <div id="wechat_bridge_panel" class="wechat-bridge-panel extension_settings" style="padding: 15px; margin-top: 15px; background: rgba(0,0,0,0.2); border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
            
            <h3 class="wechat-bridge-title" style="margin-top: 0; margin-bottom: 15px; font-size: 1.2em;">
                <i class="fa-solid fa-comment-dots"></i> WeChat Bridge
            </h3>

            <div style="margin-bottom: 15px; font-size: 14px;">
                <b>状态:</b> <span id="wechat_status_text" class="wechat-status" style="font-weight: bold; color: #ffcc00;">等待连接...</span>
            </div>

            <div id="wechat_qr_container" class="wechat-qr-wrapper" style="display: none; margin-bottom: 15px;">
                <img id="wechat_qr_img" alt="WeChat Login QR" style="display:none; width:200px; height:200px; margin: 0 auto;" />
                
                <div id="wechat_qr_link_box" style="display:none; text-align: center; padding: 15px; background: rgba(0, 0, 0, 0.4); border-radius: 8px; border: 1px dashed #555;">
                    <a id="wechat_qr_link" href="#" target="_blank" style="font-size: 16px; font-weight: bold; color: #00aaff; text-decoration: underline;">
                        <i class="fa-solid fa-external-link-alt"></i> 点击此处打开微信登录二维码
                    </a>
                    <div style="font-size: 12px; color: #aaa; margin-top: 8px;">(请在新弹出的网页中使用手机微信扫码)</div>
                </div>
            </div>

            <div class="wechat-control-row" style="margin-bottom: 15px;">
                <label for="wechat_character_select" class="wechat-label" style="display: block; margin-bottom: 8px; font-weight: bold;">绑定角色</label>
                <select id="wechat_character_select" class="text_pole" style="width: 100%; padding: 8px;"></select>
            </div>

            <div class="wechat-control-row" style="margin-bottom: 15px; display: flex; align-items: center;">
                <input type="checkbox" id="ws_auto_connect" style="margin-right: 8px;">
                <label for="ws_auto_connect" style="cursor: pointer;">启动时自动监听</label>
            </div>

            <div class="wechat-control-row">
                <button id="wechat_connect_btn" class="menu_button" style="width: 100%; padding: 10px; font-weight: bold;">
                    获取登录二维码
                </button>
            </div>
        </div>
    `;

    $('#extensions_settings').append(inlineHtml);
}

function initAfterHtmlLoaded() {
    cacheElements();
    initCharacterSelect();
    bindEvents();
    updateConnectionButtons(false);

    if (extension_settings[extensionName].autoConnect) {
        setStatus('自动连接已启用，正在连接...');
        startQrPolling();
    } else {
        setStatus('扩展初始化完成，等待连接...');
    }
}

jQuery(async () => {
    try {
        await appendSettingsHtml();
        initAfterHtmlLoaded();
    } catch (error) {
        console.error(`[${extensionName}] 加载扩展设置页面失败`, error);
    }
});