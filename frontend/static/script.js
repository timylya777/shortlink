// ======================
// ТЁМНАЯ ТЕМА
// ======================

// Применяем тему
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    const icon = document.getElementById('theme-icon');
    const text = document.getElementById('theme-text');
    
    if (theme === 'dark') {
        icon.classList.remove('fa-moon');
        icon.classList.add('fa-sun');
        text.textContent = 'Светлая';
    } else {
        icon.classList.remove('fa-sun');
        icon.classList.add('fa-moon');
        text.textContent = 'Тёмная';
    }
}
// Регистрация
await fetch('/register', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    username: 'test',
    password: 'test123',
    email: 'test@example.com'
  })
});

// Вход
await fetch('/login', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    username: 'test',
    password: 'test123'
  }),
  credentials: 'include'
});

// Проверка авторизации
await fetch('/me', {
  credentials: 'include'
});

// Переключаем тему
function toggleTheme() {
    const currentTheme = localStorage.getItem('theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
}

// Проверяем системные настройки и сохранённую тему
function checkTheme() {
    // Проверяем сохранённую тему
    const savedTheme = localStorage.getItem('theme');
    
    // Проверяем системные настройки
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme) {
        applyTheme(savedTheme);
    } else if (systemPrefersDark) {
        applyTheme('dark');
    }
}

// ======================
// ОСНОВНЫЕ ФУНКЦИИ
// ======================

// Копирование в буфер обмена
function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => {
            showNotification('Ссылка скопирована!');
        })
        .catch(err => {
            console.error('Ошибка копирования:', err);
            showNotification('Не удалось скопировать', true);
        });
}

// Показать уведомление
function showNotification(message, isError = false) {
    const notification = document.createElement('div');
    notification.className = 'copy-notification';
    notification.textContent = message;
    
    if (isError) {
        notification.style.background = '#dc3545';
    }
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 2000);
}

// Сокращение URL
async function shortenUrl() {
    const originalUrl = document.getElementById('originalUrl').value.trim();
    if (!originalUrl) {
        showNotification('Введите ссылку!', true);
        return;
    }

    try {
        const response = await fetch('/shorten', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ original_url: originalUrl })
        });

        if (!response.ok) {
            throw new Error('Ошибка сервера');
        }

        const data = await response.json();
        const resultDiv = document.getElementById('result');
        
        resultDiv.innerHTML = `
            <div class="link-item">
                <div class="link-controls">
                    <a href="${data.short_url}" class="short-url" target="_blank">${data.short_url}</a>
                    <button class="copy-btn" onclick="copyToClipboard('${data.short_url}')">
                        <i class="fas fa-copy"></i> Копировать
                    </button>
                </div>
                <div class="original-url">→ ${data.original_url}</div>
            </div>
        `;
        
        document.getElementById('originalUrl').value = '';
        
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка при сокращении ссылки', true);
    }
}

// ======================
// ИНИЦИАЛИЗАЦИЯ
// ======================
function setActivePage() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // Устанавливаем активную страницу
    setActivePage();
    
    // Инициализация темы
    checkTheme();
    
    // Обработчик для системных изменений темы
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('theme')) {
            applyTheme(e.matches ? 'dark' : 'light');
        }
    });
    
    // Инициализация основной функциональности
    if (document.getElementById('originalUrl')) {
        // Код для index.html
        document.getElementById('originalUrl').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                shortenUrl();
            }
        });
    }
});
