const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const origin = 'http://127.0.0.1:18743';
const models = ['spain-repro', 'spain-paired-control', 'spain-structured-control'];

(async () => {
    const browser = await chromium.launch({ channel: 'chrome', headless: true });
    try {
        const page = await browser.newPage();
        page.on('console', msg => {
            if (msg.type() === 'error') console.error('browser:', msg.text().slice(0, 250));
        });
        for (const model of models) {
            await page.goto(origin + '/?models=' + model);
            await page.locator('#chat-input').waitFor({ timeout: 60000 });
            const dismissReleaseNotes = page.getByRole('button', { name: "Okay, Let's Go!" });
            if (await dismissReleaseNotes.isVisible()) await dismissReleaseNotes.click();
            const prompt = 'Reply with only the number forty-two.';
            await page.locator('#chat-input').fill(prompt);
            await Promise.all([
                page.waitForRequest(req => req.url() === origin + '/api/chat/completions' &&
                    req.method() === 'POST' && req.postDataJSON()?.model === model),
                page.locator('#send-message-button').click(),
            ]);
            await page.waitForURL(/\/c\/[a-f0-9-]+/, { timeout: 30000 });
            await page.waitForFunction(() => document.querySelector('main')?.innerText.includes('42'));
            const chatPath = new URL(page.url()).pathname;
            const chatId = chatPath.split('/').at(-1);
            let persisted;
            for (let probe = 0; probe < 20; probe++) {
                persisted = await page.evaluate(async (id) => {
                    const token = localStorage.getItem('token');
                    return await (await fetch('/api/v1/chats/' + id, {
                        headers: {Authorization: 'Bearer ' + token}
                    })).json();
                }, chatId);
                if (Object.values(persisted.chat?.history?.messages ?? {}).some(m => m.role === 'assistant' && m.done && m.output?.length)) break;
                await page.waitForTimeout(250);
            }
            const answer = Object.values(persisted.chat.history.messages).find(m => m.role === 'assistant');
            assert(answer.done);
            const messageText = answer.output.filter(x => x.type === 'message').flatMap(x => x.content).map(x => x.text).join('');
            const kinds = answer.output.map(x => x.type);
            const visible = await page.locator('main').innerText();
            if (model === models[0]) {
                assert.equal(messageText, 'Audit preface.</think>42');
                assert(visible.includes('</think>'));
                assert(!kinds.includes('reasoning'));
            } else {
                assert.equal(messageText, '42');
                assert(kinds.includes('reasoning'));
                assert(!visible.includes('</think>'));
            }
            await page.reload();
            await page.waitForFunction(() => document.querySelector('main')?.innerText.includes('42'));
            assert.equal((await page.locator('main').innerText()).includes('</think>'), model === models[0]);
            console.log(JSON.stringify({model, outputTypes: kinds, savedAnswer: messageText, rawMarkerAfterReload: model === models[0]}));
        }
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
