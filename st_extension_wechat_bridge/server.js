const express = require('express');

const router = express.Router();
let messageQueue = [];

router.post('/receive', (req, res) => {
    const { user_id, content } = req.body || {};

    if (!user_id || !content) {
        return res.status(400).json({
            status: 'error',
            message: 'Missing required fields: user_id, content',
        });
    }

    messageQueue.push({
        user_id: String(user_id),
        content: String(content),
        timestamp: Date.now(),
    });

    return res.json({ status: 'ok' });
});

router.get('/queue', (_req, res) => {
    const queued = [...messageQueue];
    messageQueue = [];
    return res.json(queued);
});

module.exports = router;
