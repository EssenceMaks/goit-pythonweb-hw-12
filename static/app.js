// Утилитная функция для выполнения fetch с JWT-авторизацией
async function authorizedFetch(url, options = {}) {
  // Формируем базовые настройки запроса
  const fetchOptions = {
    ...options,
    headers: {
      ...options.headers,
      'Content-Type': 'application/json'
    },
    credentials: 'include' // Важно для отправки cookies
  };
  
  // Выполняем запрос
  try {
    const response = await fetch(url, fetchOptions);
    
    // Проверка статуса
    if (response.status === 401) {
      console.error('Не авторизован. Перенаправление на страницу входа');
      window.location.href = '/login';
      return null;
    }
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Ошибка запроса: ${response.status}`);
    }
    
    // Пытаемся распарсить ответ как JSON, но не ломаемся если это не JSON
    try {
      return await response.json();
    } catch (e) {
      return response;
    }
  } catch (error) {
    console.error('Ошибка при выполнении запроса:', error);
    throw error;
  }
}

async function dbAction(action) {
  let endpoint = '';
  if (action === 'init') endpoint = '/db/init';
  if (action === 'fill') endpoint = '/db/fill-fake';
  if (action === 'clear') endpoint = '/db/clear';
  let params = {};
  if (action === 'fill') params = { n: 10 };
  const btn = document.getElementById(`btn-${action}`);
  btn.disabled = true;
  btn.innerText = '...';
  try {
    // Используем authorizedFetch
    const data = await authorizedFetch(endpoint + (action === 'fill' ? '?n=10' : ''), { method: 'POST' });
    
    // Зберігаємо інформацію про користувача в sessionStorage при завантаженні сторінки
    if (document.cookie) {
      const userMatch = document.cookie.match(/user=([^;]*)/);
      if (userMatch && userMatch[1]) {
        try {
          const user = JSON.parse(userMatch[1]);
          if (user) {
            sessionStorage.setItem('user', JSON.stringify(user));
          }
        } catch (e) {
          console.error('Ошибка парсинга cookie user:', e);
        }
      }
    }
    alert(data.message || JSON.stringify(data));
  } catch (e) {
    alert('Ошибка: ' + e.message);
  }
  btn.disabled = false;
  if (action === 'init') btn.innerText = 'Создать шаблон базы';
  if (action === 'fill') btn.innerText = 'Создать случайные контакты';
  if (action === 'clear') btn.innerText = 'Удалить все контакты';
}
