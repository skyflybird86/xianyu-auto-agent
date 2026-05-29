console.log('🐟 闲鱼Cookie获取助手已加载');

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getCookies') {
        // 获取页面cookie（非HttpOnly）
        const pageCookies = document.cookie;
        sendResponse({ pageCookies: pageCookies });
    }
});