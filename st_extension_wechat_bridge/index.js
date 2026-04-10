(() => {
    'use strict';

    const PYTHON_BASE = 'http://127.0.0.1:8080/api';
    const ST_QUEUE_API = '/api/extensions/wechat_bridge/queue';
    const ST_SEND_TEXTAREA = '#send_textarea';
    const ST_SEND_BUTTON = '#send_but';

    const $statusText = $('#wechat_status_text');
    const $qrImg = $('#wechat_qr_img');
    const $characterSelect = $('#wechat_character_select');
    const $connectBtn = $('#wechat_connect_btn');

    let qrTimer = null;
    let queueTimer = null;
    let lastWechatUserId = null;

    function setStatus(text) {
        $statusText.text(text);
    }

    function getCharactersArray() {
        if (Array.isArray(window.characters)) {
            return window.characters;
        }
        return [];
    }

    function initCharacterSelect() {
        const list = getCharactersArray();
        $characterSelect.empty();

        list.forEach((char, index) => {
            const name = (char && char.name) ? String(char.name) : `角色${index + 1}`;
            $characterSelect.append(`<option value="${name}">${name}</option>`);
        });

        if (list.length === 0) {
            $characterSelect.append('<option value="">无可用角色</option>');
        }
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

    async function pollQrCode() {
        try {
            const resp = await fetch(`${PYTHON_BASE}/qrcode`, { method: 'GET' });
            if (!resp.ok) return;

            const data = await resp.json();
            const status = data?.status;
            const qrData = data?.qr_data;

            if (typeof qrData === 'string' && /^https?:\/\//i.test(qrData)) {
                const qrRenderUrl =
                    'https://api.qrserver.com/v1/create-qr-code/?size=256x256&data=' +
                    encodeURIComponent(qrData);
                $qrImg.attr('src', qrRenderUrl).show();
                setStatus('请使用微信扫码登录...');
            }

            if (status === 'logged_in') {
                stopQrPolling();
                $qrImg.hide();
                setStatus('微信已登录，开始监听消息');
                startQueuePolling();
            }
        } catch (_err) {
            setStatus('二维码轮询失败，等待重试...');
        }
    }

    function isSelectedCharacterActive() {
        const selectedName = $characterSelect.val();
        if (!selectedName) return false;

        const chars = getCharactersArray();
        const activeChid = Number(window.this_chid);

        if (Number.isInteger(activeChid) && activeChid >= 0 && chars[activeChid]) {
            const activeName = chars[activeChid]?.name;
            return String(activeName || '') === String(selectedName);
        }

        // 无法判断当前聊天角色时，默认放行，避免阻塞桥接。
        return true;
    }

    function injectMessageToSt(content) {
        $(ST_SEND_TEXTAREA).val(content);
        $(ST_SEND_BUTTON).click();
    }

    async function pollQueue() {
        try {
            const resp = await fetch(ST_QUEUE_API, { method: 'GET' });
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

                setStatus(`收到微信消息：${lastWechatUserId}`);
                injectMessageToSt(String(content));
            }
        } catch (_err) {
            setStatus('消息轮询失败，等待重试...');
        }
    }

    function startQueuePolling() {
        stopQueuePolling();
        queueTimer = setInterval(pollQueue, 2000);
        pollQueue();
    }

    function extractReplyText(eventData) {
        const raw =
            eventData?.message?.mes ||
            eventData?.mes ||
            eventData?.text ||
            eventData?.message ||
            '';

        const plain = String(raw)
            .replace(/\*.*?\*/g, '')
            .replace(/\n{3,}/g, '\n\n')
            .trim();

        return plain;
    }

    async function sendReplyToWechat(text) {
        if (!lastWechatUserId || !text) return;

        try {
            await fetch(`${PYTHON_BASE}/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: lastWechatUserId,
                    content: text,
                }),
            });
        } catch (_err) {
            setStatus('回传微信失败，等待下次回复重试...');
        }
    }

    function bindEvents() {
        $connectBtn.on('click', () => {
            setStatus('正在获取二维码...');
            stopQrPolling();
            qrTimer = setInterval(pollQrCode, 3000);
            pollQrCode();
        });

        if (window.eventSource && typeof window.eventSource.on === 'function') {
            window.eventSource.on('characterMessageRendered', async (eventData) => {
                const cleanText = extractReplyText(eventData);
                if (!cleanText) return;
                await sendReplyToWechat(cleanText);
            });
        }
    }

    function init() {
        initCharacterSelect();
        bindEvents();
        setStatus('等待连接...');
    }

    init();
})();
