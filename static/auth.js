// Утилитная функция для выполнения fetch с JWT-авторизацией
async function authorizedFetch(url, options = {}) {
  console.log(`authorizedFetch: ${url}`, options);
  
  // Формируем базовые настройки запроса
  const fetchOptions = {
    ...options,
    headers: {
      ...options.headers,
      'Content-Type': 'application/json'
    },
    credentials: 'include' // Важно для отправки cookies
  };
  
  // Добавляем токен из куки как заголовок Authorization
  let tokenValue = null;
  
  try {
    // Используем оригинальный метод извлечения токена
    const tokenMatch = document.cookie.match(/access_token=([^;]*)/);
    if (tokenMatch) {
      tokenValue = tokenMatch[1];
      console.log('Токен успешно извлечен из куки через регулярное выражение');
    } 
    // Резервный метод, если оригинальный не сработал
    else {
      console.log('Попытка извлечь токен через перебор кук');
      const cookies = document.cookie.split(';');
      
      for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith('access_token=')) {
          tokenValue = cookie.substring('access_token='.length);
          console.log('Токен успешно извлечен через перебор кук');
          break;
        }
      }
    }
  } catch (error) {
    console.error('Ошибка при извлечении токена из куки:', error);
  }
  
  // Если токен найден, добавляем его в заголовки
  if (tokenValue) {
    // Токен может быть уже с префиксом "Bearer " или без него
    const authHeader = tokenValue.startsWith('Bearer ') 
      ? tokenValue 
      : `Bearer ${tokenValue}`;
    
    fetchOptions.headers = {
      ...fetchOptions.headers,
      'Authorization': authHeader
    };
    
    console.log('Добавлен заголовок авторизации из куки');
  } else {
    console.log('Токен в куки не найден');
  }
  
  // Выполняем запрос
  try {
    console.log(`Sending request to ${url} with options:`, fetchOptions);
    const response = await fetch(url, fetchOptions);
    console.log(`Got response from ${url}:`, response.status);
    
    // Проверка статуса
    if (response.status === 401) {
      console.error('Не авторизован. Перенаправление на страницу входа');
      window.location.href = '/login'; // Включаем автоматический редирект при 401
      return null;
    }
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error(`Error response from ${url}:`, errorData);
      throw new Error(errorData.detail || `Ошибка запроса: ${response.status}`);
    }
    
    // Пытаемся распарсить ответ как JSON, но не ломаемся если это не JSON
    if (response.status !== 204) { // Если статус не "No Content"
      try {
        const data = await response.json();
        console.log(`Success response from ${url}:`, data);
        return data;
      } catch (e) {
        console.log(`Response is not JSON from ${url}`);
        return response;
      }
    }
    return {}; // Для DELETE/PUT операций, которые могут не возвращать JSON
  } catch (error) {
    console.error('Ошибка при выполнении запроса:', error);
    throw error;
  }
}

// Для поддержки старых версий fetch во всех скриптах
// Переопределяем глобальный fetch для автоматического включения авторизации
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
  console.log(`[Patched fetch] ${url}`);
  
  // Для всех запросов к API автоматически добавляем credentials
  options = options || {};
  options.credentials = 'include';
  
  return originalFetch(url, options);
};

// Экспортируем authorizedFetch как глобальную функцию
window.authorizedFetch = authorizedFetch;

// Проверяем наличие jwt при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
  console.log('auth.js загружен');
  console.log('JWT token в cookies:', document.cookie.includes('access_token'));
});