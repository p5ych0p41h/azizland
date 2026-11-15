const SERVER_STATUS_QUERY = 'azizland.ru';

function copyIp(address, buttonId) {
    const fallbackCopy = () => {
        const input = document.createElement('textarea');
        input.value = address;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(address).catch(fallbackCopy);
    } else {
        fallbackCopy();
    }

    if (buttonId) {
        const btn = document.getElementById(buttonId);
        if (btn) {
            const original = btn.textContent;
            btn.textContent = 'Скопировано';
            setTimeout(() => {
                btn.textContent = original;
            }, 1800);
        }
    }

    showToast('Адрес «' + address + '» скопирован в буфер обмена');
}

function showToast(message) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('visible');
    clearTimeout(window.__toastTimer);
    window.__toastTimer = setTimeout(() => {
        toast.classList.remove('visible');
    }, 2800);
}

async function refreshServerStatus() {
    try {
        const res = await fetch('https://api.mcstatus.io/v2/status/java/' + SERVER_STATUS_QUERY);
        if (!res.ok) return;
        const data = await res.json();

        const navStatusText = document.getElementById('navStatusText');
        const navStatusDot = document.getElementById('navStatusDot');
        const onlineMetric = document.getElementById('onlineCount');

        if (data.online) {
            const current = data.players ? data.players.online : 0;
            const max = data.players ? data.players.max : 50;
            if (navStatusText) {
                navStatusText.textContent = 'Онлайн: ' + current + ' из ' + max;
            }
            if (navStatusDot) {
                navStatusDot.style.backgroundColor = '#16a34a';
            }
            if (onlineMetric) {
                onlineMetric.textContent = current + ' из ' + max;
            }
        } else {
            if (navStatusText) {
                navStatusText.textContent = 'В сети';
            }
            if (navStatusDot) {
                navStatusDot.style.backgroundColor = '#16a34a';
            }
        }
    } catch (e) {
        // Silent fallback if status API is unreachable
    }
}

document.addEventListener('DOMContentLoaded', () => {
    refreshServerStatus();
    setInterval(refreshServerStatus, 20000);
});
