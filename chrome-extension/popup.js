// 保存当前获取到的Cookie字符串
let currentCookieString = '';

// 关键Cookie字段
const REQUIRED_COOKIES = ['unb', '_tb_token_', 'cookie2'];
const IMPORTANT_COOKIES = ['unb', '_tb_token_', 'cookie2', 'csg', 't', '_m_h5_tk', '_m_h5_tk_enc'];

async function getCookie() {
    const statusDiv = document.getElementById('status-info');
    const cookieSection = document.getElementById('cookie-section');
    const cookieContent = document.getElementById('cookie-content');
    const getCookieBtn = document.getElementById('get-cookie-btn');
    
    try {
        statusDiv.className = 'status info';
        statusDiv.innerHTML = '<div class="icon">🔄</div><div>正在获取Cookie...</div>';
        getCookieBtn.disabled = true;
        
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url || (!tab.url.includes('goofish.com') && !tab.url.includes('xianyu.com') && !tab.url.includes('taobao.com'))) {
            statusDiv.className = 'status error';
            statusDiv.innerHTML = '<div class="icon">❌</div><div>请先打开闲鱼网站</div>';
            getCookieBtn.disabled = false;
            return;
        }
        
        // 获取当前页面的域名
        const url = new URL(tab.url);
        const currentDomain = url.origin;
        
        // 尝试多个域名获取Cookie
        const domains = [
            currentDomain,
            'https://www.goofish.com',
            'https://2.taobao.com',
            'https://www.taobao.com',
            'https://xianyu.com'
        ];
        
        let allCookies = [];
        
        for (const domain of domains) {
            try {
                const cookies = await chrome.cookies.getAll({ url: domain });
                allCookies = [...allCookies, ...cookies];
            } catch (e) {
                console.log(`无法从 ${domain} 获取Cookie:`, e);
            }
        }
        
        // 去重（保留最新的）
        const cookieMap = new Map();
        allCookies.forEach(c => {
            if (!cookieMap.has(c.name) || c.expirationDate > cookieMap.get(c.name).expirationDate) {
                cookieMap.set(c.name, c);
            }
        });
        
        if (cookieMap.size === 0) {
            statusDiv.className = 'status error';
            statusDiv.innerHTML = '<div class="icon">❌</div><div>未找到Cookie，请先登录闲鱼</div>';
            getCookieBtn.disabled = false;
            return;
        }
        
        // 检查关键Cookie
        const foundCookies = Array.from(cookieMap.keys());
        const missingRequired = REQUIRED_COOKIES.filter(name => !foundCookies.includes(name));
        const foundImportant = IMPORTANT_COOKIES.filter(name => foundCookies.includes(name));
        
        currentCookieString = Array.from(cookieMap.entries())
            .map(([name, cookie]) => `${name}=${cookie.value}`)
            .join('; ');
        
        cookieContent.textContent = currentCookieString;
        
        if (missingRequired.length === 0) {
            statusDiv.className = 'status success';
            statusDiv.innerHTML = `<div class="icon">✅</div><div>Cookie获取成功<br><small>已找到关键字段: ${foundImportant.join(', ')}</small></div>`;
        } else {
            statusDiv.className = 'status warning';
            statusDiv.innerHTML = `<div class="icon">⚠️</div><div>Cookie已获取但缺少关键字段<br><small>缺少: ${missingRequired.join(', ')}<br>建议刷新页面后重试</small></div>`;
        }
        
        cookieSection.classList.remove('hidden');
        getCookieBtn.classList.add('hidden');
        
        await navigator.clipboard.writeText(currentCookieString);
        
        showCopiedToast();
        
    } catch (error) {
        console.error('获取Cookie失败:', error);
        statusDiv.className = 'status error';
        statusDiv.innerHTML = `<div class="icon">❌</div><div>获取失败: ${error.message}</div>`;
        getCookieBtn.disabled = false;
    }
}

async function copyCookie() {
    try {
        if (currentCookieString) {
            await navigator.clipboard.writeText(currentCookieString);
            showCopiedToast();
        }
    } catch (error) {
        console.error('复制失败:', error);
        alert('复制失败，请手动复制');
    }
}

async function openConfigPage() {
    try {
        const configUrl = 'http://localhost:8080';
        
        await chrome.tabs.create({ url: configUrl, active: true });
        
        if (currentCookieString) {
            setTimeout(async () => {
                try {
                    const response = await fetch(`${configUrl}/api/config`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            COOKIES_STR: currentCookieString
                        })
                    });
                    
                    if (response.ok) {
                        showToast('✅ Cookie已自动填充到配置页面');
                    } else {
                        showToast('⚠️ 请手动粘贴Cookie到配置页面');
                    }
                } catch (error) {
                    console.error('自动填充失败:', error);
                    showToast('⚠️ 请手动粘贴Cookie到配置页面');
                }
            }, 1000);
        }
        
    } catch (error) {
        console.error('打开配置页面失败:', error);
        alert('无法打开配置页面，请手动访问 http://localhost:5000');
    }
}

async function refreshCookie() {
    const cookieContent = document.getElementById('cookie-content');
    const statusDiv = document.getElementById('status-info');
    
    try {
        statusDiv.className = 'status info';
        statusDiv.innerHTML = '<div class="icon">🔄</div><div>正在刷新Cookie...</div>';
        
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url || (!tab.url.includes('goofish.com') && !tab.url.includes('xianyu.com') && !tab.url.includes('taobao.com'))) {
            statusDiv.className = 'status error';
            statusDiv.innerHTML = '<div class="icon">❌</div><div>请先打开闲鱼网站</div>';
            return;
        }
        
        const url = new URL(tab.url);
        const currentDomain = url.origin;
        
        const domains = [
            currentDomain,
            'https://www.goofish.com',
            'https://2.taobao.com',
            'https://www.taobao.com'
        ];
        
        let allCookies = [];
        
        for (const domain of domains) {
            try {
                const cookies = await chrome.cookies.getAll({ url: domain });
                allCookies = [...allCookies, ...cookies];
            } catch (e) {
                console.log(`无法从 ${domain} 获取Cookie:`, e);
            }
        }
        
        const cookieMap = new Map();
        allCookies.forEach(c => {
            if (!cookieMap.has(c.name) || c.expirationDate > cookieMap.get(c.name).expirationDate) {
                cookieMap.set(c.name, c);
            }
        });
        
        currentCookieString = Array.from(cookieMap.entries())
            .map(([name, cookie]) => `${name}=${cookie.value}`)
            .join('; ');
        
        cookieContent.textContent = currentCookieString;
        statusDiv.className = 'status success';
        statusDiv.innerHTML = '<div class="icon">✅</div><div>Cookie刷新成功</div>';
        
        await navigator.clipboard.writeText(currentCookieString);
        showCopiedToast();
        
    } catch (error) {
        console.error('刷新Cookie失败:', error);
        statusDiv.className = 'status error';
        statusDiv.innerHTML = `<div class="icon">❌</div><div>刷新失败: ${error.message}</div>`;
    }
}

function showCopiedToast() {
    const toast = document.getElementById('copied-toast');
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2000);
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0,0,0,0.9);
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        font-size: 14px;
        z-index: 99999;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

async function checkStatus() {
    const statusDiv = document.getElementById('status-info');
    const getCookieBtn = document.getElementById('get-cookie-btn');
    
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (tab.url && (tab.url.includes('goofish.com') || tab.url.includes('xianyu.com') || tab.url.includes('taobao.com'))) {
            statusDiv.className = 'status info';
            statusDiv.innerHTML = '<div class="icon">👌</div><div>已在闲鱼页面，点击获取Cookie</div>';
            getCookieBtn.disabled = false;
        } else {
            statusDiv.className = 'status error';
            statusDiv.innerHTML = '<div class="icon">⚠️</div><div>请先打开闲鱼网站</div>';
            getCookieBtn.disabled = false;
        }
    } catch (error) {
        console.error('检查状态失败:', error);
    }
}

// 当DOM加载完成后绑定所有事件监听器
document.addEventListener('DOMContentLoaded', function() {
    // 绑定按钮事件
    document.getElementById('get-cookie-btn').addEventListener('click', getCookie);
    document.getElementById('copy-btn').addEventListener('click', copyCookie);
    document.getElementById('open-config-btn').addEventListener('click', openConfigPage);
    document.getElementById('refresh-btn').addEventListener('click', refreshCookie);
    
    // 检查初始状态
    checkStatus();
});
