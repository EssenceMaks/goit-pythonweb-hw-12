// JS для меню

// Открытие попапа создания контакта
function openPopup(id) {
  document.getElementById(id).style.display = 'block';
}
function closePopup(id) {
  document.getElementById(id).style.display = 'none';
}

// --- Функция для загрузки профиля пользователя и обновления аватара в меню ---
async function loadUserProfile() {
  try {
    console.log('Загрузка профиля пользователя для аватара в меню...');
    
    // Проверяем наличие функции для выполнения авторизованных запросов
    const fetchFunction = window.authorizedFetch || window.authorizedRequest;
    
    if (!fetchFunction) {
      console.error('Функции authorizedFetch или authorizedRequest не найдены!');
      return;
    }
    
    // Выполняем запрос к API для получения информации о текущем пользователе
    const userData = await fetchFunction('/users/me');
    
    if (!userData) {
      console.error('Не удалось получить данные пользователя для обновления аватара');
      return;
    }
    
    console.log('Получены данные пользователя для аватара:', userData);
    
    // Обновляем аватар в меню, если он есть
    if (userData.avatar_url) {
      const menuAvatarElement = document.querySelector('.avatar-section img');
      if (menuAvatarElement) {
        menuAvatarElement.src = userData.avatar_url;
        menuAvatarElement.alt = userData.username || 'User Avatar';
      }
    }
    
    // Обновляем имя пользователя в меню
    if (userData.username) {
      // Обновляем имя в выпадающем меню
      const usernameInMenu = document.querySelector('.username-in-menu');
      if (usernameInMenu) {
        usernameInMenu.textContent = userData.username;
      }
      
      // Обновляем имя в блоке верхнего меню (div.user-info .username)
      const usernameElement = document.querySelector('.user-info .username');
      if (usernameElement) {
        usernameElement.textContent = userData.username;
      }
      
      // Обновляем глобальную переменную с именем пользователя, если она существует
      if (typeof window.currentUsername !== 'undefined') {
        window.currentUsername = userData.username;
      }
    }
    
  } catch (error) {
    console.error('Ошибка при загрузке профиля пользователя:', error);
  }
}

// Экспортируем функцию для использования в других модулях
window.loadUserProfile = loadUserProfile;

// --- Логика для сообщений в футере ---
function addFooterMessage(msg, type = 'info') {
  let log = JSON.parse(localStorage.getItem('footerLog') || '[]');
  log.push({msg, type, ts: Date.now()});
  localStorage.setItem('footerLog', JSON.stringify(log));
  renderFooterMessages();
}
function renderFooterMessages(showAll = false) {
  let log = JSON.parse(localStorage.getItem('footerLog') || '[]');
  const footer = document.getElementById('footer-message');
  const btn = document.getElementById('footer-log-toggle');
  if (!footer) return;
  if (!log.length) {
    footer.style.display = 'none';
    if (btn) btn.style.display = 'none';
    return;
  }
  footer.style.display = 'block';
  let toShow = showAll ? log.slice(-15) : log.slice(-5);
  // Новые сверху
  toShow = toShow.reverse();
  footer.innerHTML = toShow.map(l => `<div class="footer-row ${l.type}">${l.msg}</div>`).join('');
  if (btn) {
    btn.style.display = log.length > 5 ? 'inline-block' : 'none';
    btn.textContent = showAll ? 'Сховати' : 'Показати всі';
    btn.onclick = () => {
      footer.classList.toggle('expanded', !showAll);
      renderFooterMessages(!showAll);
    };
    // Управляем высотой футера
    footer.classList.toggle('expanded', showAll);
  }
  // Скроллим к последнему сообщению, если expanded
  if (showAll) footer.scrollTop = footer.scrollHeight;
}
window.addFooterMessage = addFooterMessage;
window.renderFooterMessages = renderFooterMessages;
document.addEventListener('DOMContentLoaded', ()=>renderFooterMessages());

// --- Модификация checkDBState для футера ---
async function checkDBState() {
  try {
    console.log('Проверка состояния базы данных...');
    
    // Используем обновленную функцию getAuthHeader для получения заголовка авторизации
    const authHeader = getAuthHeader();
    
    const response = await fetch('/db/check-state', {
      method: 'GET',
      headers: {
        ...authHeader,
        'Accept': 'application/json'
      },
      credentials: 'include' // Важно для включения cookies
    });
    
    if (!response.ok) {
      console.error('Ошибка при проверке состояния БД:', response.statusText);
      return;
    }
    
    const resp = await response.json();
    
    if (resp.status === 'no_db' || resp.status === 'no_tables' || resp.status === 'no_contacts') {
      addFooterMessage(resp.message, resp.status === 'no_db' ? 'error' : 'warn');
    } else if (resp.status === 'ok') {
      addFooterMessage(`Контактів у базі: ${resp.count}`, 'success');
    } else if (resp.status === 'noenv') {
      addFooterMessage(resp.message, 'error');
    }
  } catch (e) {
    console.error('Ошибка при проверке состояния базы данных:', e);
  }
}

// Получение токена для авторизованных запросов
function getAuthHeader() {
  const tokenMatch = document.cookie.match(/access_token=([^;]*)/); 
  if (!tokenMatch) return {};
  
  // Токен теперь всегда без префикса "Bearer "
  const tokenValue = tokenMatch[1];
  // Добавляем префикс "Bearer " для заголовка Authorization
  return {'Authorization': `Bearer ${tokenValue}`};
}

// Получение refresh токена
function getRefreshToken() {
  const tokenMatch = document.cookie.match(/refresh_token=([^;]*)/); 
  if (!tokenMatch) return null;
  return tokenMatch[1];
}

// Обновленная функция для выполнения авторизованных запросов
async function authorizedRequest(url, options = {}) {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...getAuthHeader(),
        'Content-Type': 'application/json',
        ...options.headers
      },
      credentials: 'include' // Включаем cookies
    });
    
    // Проверка на истекший токен
    if (response.status === 401) {
      // Пробуем обновить токен
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        // Повторяем запрос с новым токеном
        const newResponse = await fetch(url, {
          ...options,
          headers: {
            ...getAuthHeader(), // Получаем новый токен
            'Content-Type': 'application/json',
            ...options.headers
          },
          credentials: 'include'
        });
        
        if (!newResponse.ok) {
          console.error(`Ошибка повторного запроса ${url}:`, newResponse.statusText);
          return null;
        }
        
        return await newResponse.json();
      }
    }
    
    if (!response.ok) {
      console.error(`Ошибка запроса ${url}:`, response.statusText);
      return null;
    }
    
    return await response.json();
  } catch (e) {
    console.error(`Ошибка при выполнении запроса ${url}:`, e);
    return null;
  }
}

// Функция для обновления access_token с помощью refresh_token
async function refreshAccessToken() {
  try {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      console.error('Нет refresh_token для обновления');
      return false;
    }
    
    const response = await fetch('/auth/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include' // Включаем cookies
    });
    
    if (!response.ok) {
      console.error('Ошибка обновления токена:', response.statusText);
      return false;
    }
    
    const data = await response.json();
    return true;
  } catch (e) {
    console.error('Ошибка при обновлении токена:', e);
    return false;
  }
}

// Функция для проверки статуса аккаунта
async function checkAccountStatus(userId) {
  try {
    const response = await fetch(`/auth/status?user_id=${userId}`, {
      credentials: 'include'
    });
    
    if (!response.ok) {
      return { status: 'error', message: 'Ошибка при проверке статуса' };
    }
    
    return await response.json();
  } catch (e) {
    console.error('Ошибка при проверке статуса аккаунта:', e);
    return { status: 'error', message: e.message };
  }
}

// Вывод сообщения в футер
function showFooterMessage(msg, type = 'info') {
  addFooterMessage(msg, type);
}

// --- Глобальная функция для сброса фильтров и обновления контактов ---
window.resetAndRenderContacts = function() {
  // Сбросить фильтры поиска, сортировки, дней рождения
  if (window.resetContactsUI) window.resetContactsUI();
  if (window.fetchAndRenderContacts) window.fetchAndRenderContacts();
};

// Кнопки меню для работы с БД
document.addEventListener('DOMContentLoaded', function() {
  // Проверяем наличие функции authorizedFetch перед вызовом checkDBState
  if (window.authorizedFetch) {
    checkDBState();
    
    // Загружаем профиль пользователя при загрузке страницы
    loadUserProfile();
  } else {
    console.error('authorizedFetch не найден! Убедитесь, что auth.js загружен до menu.js');
    setTimeout(() => {
      if (window.authorizedFetch) {
        console.log('authorizedFetch появился с задержкой, выполняем checkDBState');
        checkDBState();
        
        // Загружаем профиль пользователя с задержкой
        loadUserProfile();
      }
    }, 500);
  }
  
  const btnCreate = document.getElementById('btn-create-contact');
  if (btnCreate) {
    btnCreate.addEventListener('click', function() {
      openPopup('popup-create-contact');
    });
  }

  const btnCreateDB = document.getElementById('btn-create-db');
  const btnInit = document.getElementById('btn-init');
  const btnDropDB = document.getElementById('btn-drop-db');
  const btnFill = document.getElementById('btn-fill');
  const btnClear = document.getElementById('btn-clear');

  if (btnCreateDB) {
    btnCreateDB.addEventListener('click', async function() {
      btnCreateDB.disabled = true;
      addFooterMessage('Створення бази...', 'info');
      try {
        // 1. Створити базу - використовуємо authorizedRequest
        const resp = await authorizedRequest('/db/create-db', {method:'POST'});
        if (!resp) {
          addFooterMessage('Помилка авторизації при створенні бази', 'error');
          btnCreateDB.disabled = false;
          return;
        }
        
        if (resp.status === 'created' || resp.status === 'exists') {
          addFooterMessage(resp.message, 'success');
          // 2. Ініціалізувати таблиці - використовуємо authorizedRequest
          const resp2 = await authorizedRequest('/db/init', {method:'POST'});
          if (!resp2) {
            addFooterMessage('Помилка авторизації при ініціалізації таблиць', 'error');
            btnCreateDB.disabled = false;
            return;
          }
          
          if (resp2.status === 'created' || resp2.status === 'exists') {
            addFooterMessage('База і таблиці готові!', 'success');
            window.resetAndRenderContacts();
          } else {
            addFooterMessage('Помилка ініціалізації таблиць', 'error');
          }
        } else if (resp.status === 'noenv') {
          addFooterMessage(resp.message, 'error');
        } else {
          addFooterMessage(resp.message || 'Помилка створення бази', 'error');
        }
      } catch (e) {
        console.error('Помилка при створенні бази:', e);
        addFooterMessage('Помилка при створенні бази: ' + e.message, 'error');
      }
      btnCreateDB.disabled = false;
    });
    btnCreateDB.addEventListener('click', ()=>setTimeout(checkDBState, 1000));
  }

  if (btnDropDB) {
    btnDropDB.addEventListener('click', async function() {
      if (!confirm('Ви впевнені, що хочете ВИДАЛИТИ базу даних повністю?')) return;
      btnDropDB.disabled = true;
      addFooterMessage('Видалення бази...', 'info');
      try {
        // Використовуємо authorizedRequest
        const resp = await authorizedRequest('/db/drop-db', {method:'POST'});
        if (!resp) {
          addFooterMessage('Помилка авторизації при видаленні бази', 'error');
          btnDropDB.disabled = false;
          return;
        }
        
        if (resp.status === 'dropped') {
          addFooterMessage(resp.message, 'success');
          window.resetAndRenderContacts();
        } else {
          addFooterMessage(resp.message || 'Помилка видалення бази', 'error');
        }
      } catch (e) {
        console.error('Помилка при видаленні бази:', e);
        addFooterMessage('Помилка при видаленні бази: ' + e.message, 'error');
      }
      btnDropDB.disabled = false;
    });
    btnDropDB.addEventListener('click', ()=>setTimeout(checkDBState, 1000));
  }

  if (btnInit) {
    btnInit.addEventListener('click', async function() {
      btnInit.disabled = true;
      try {
        // Використовуємо authorizedRequest
        const resp = await authorizedRequest('/db/init', {method:'POST'});
        if (!resp) {
          addFooterMessage('Помилка авторизації при ініціалізації бази', 'error');
          btnInit.disabled = false;
          return;
        }
        
        addFooterMessage('База успішно ініціалізована', 'success');
        window.resetAndRenderContacts();
      } catch (e) {
        console.error('Помилка при ініціалізації бази:', e);
        addFooterMessage('Помилка мережі при ініціалізації: ' + e.message, 'error');
      }
      btnInit.disabled = false;
    });
  }

  if (btnFill) {
    btnFill.addEventListener('click', async function() {
      btnFill.disabled = true;
      try {
        // Використовуємо authorizedRequest
        const resp = await authorizedRequest('/db/fill-fake?n=10', {method:'POST'});
        if (!resp) {
          addFooterMessage('Помилка авторизації при додаванні контактів', 'error');
          btnFill.disabled = false;
          return;
        }
        
        addFooterMessage('Контакти успішно додані', 'success');
        window.resetAndRenderContacts();
      } catch (e) {
        console.error('Помилка при додаванні контактів:', e);
        addFooterMessage('Помилка мережі при додаванні: ' + e.message, 'error');
      }
      btnFill.disabled = false;
    });
  }

  if (btnClear) {
    btnClear.addEventListener('click', async function() {
      btnClear.disabled = true;
      try {
        // Використовуємо authorizedRequest
        const resp = await authorizedRequest('/db/clear', {method:'POST'});
        if (!resp) {
          addFooterMessage('Помилка авторизації при видаленні контактів', 'error');
          btnClear.disabled = false;
          return;
        }
        
        addFooterMessage('Всі контакти видалені', 'success');
        window.resetAndRenderContacts();
      } catch (e) {
        console.error('Помилка при видаленні контактів:', e);
        addFooterMessage('Помилка мережі при видаленні: ' + e.message, 'error');
      }
      btnClear.disabled = false;
    });
    btnClear.addEventListener('click', ()=>setTimeout(checkDBState, 1000));
  }
});

// === Permissions Logic ===
document.addEventListener('DOMContentLoaded', function() {
  if (window.userRole === 'admin' || window.userRole === 'superadmin') {
    const permLink = document.getElementById('permissions-link');
    if (permLink) {
      permLink.style.display = 'block';
      permLink.addEventListener('click', function(e) {
        e.preventDefault();
        openPermissionsModal();
      });
    }
  }
});

function openPermissionsModal() {
  let modal = document.getElementById('permissions-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'permissions-modal';
    modal.className = 'modal permissions-modal';
    modal.innerHTML = `
      <div class="modal-content">
        <span class="close-modal" onclick="closePermissionsModal()">&times;</span>
        <h2>Permissions</h2>
        <div id="permissions-users-list">Загрузка...</div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  modal.style.display = 'block';
  loadPermissionsUsers();
}
window.openPermissionsModal = openPermissionsModal;

function closePermissionsModal() {
  const modal = document.getElementById('permissions-modal');
  if (modal) modal.style.display = 'none';
}
window.closePermissionsModal = closePermissionsModal;

async function loadPermissionsUsers() {
  const container = document.getElementById('permissions-users-list');
  if (!container) return;
  try {
    const users = await (window.authorizedFetch ? window.authorizedFetch('/users/permissions') : []);
    if (!Array.isArray(users)) throw new Error('Ошибка загрузки');
    if (users.length === 0) {
      container.innerHTML = '<p>Нет пользователей</p>';
      return;
    }
    container.innerHTML = `<table class="permissions-table">
      <tr><th>Аватар</th><th>Имя</th><th>Почта</th><th>Роль</th><th>Действия</th><th>Запросы на аватар</th></tr>
      ${users.map(u => `
        <tr>
          <td><img src="${u.main_avatar_url || '/static/menu/img/avatar.png'}" style="width:40px;height:40px;border-radius:50%"></td>
          <td>${u.username}</td>
          <td>${u.email}</td>
          <td>${u.role}
            ${(u.role !== 'superadmin' && String(u.id) !== String(window.currentUserId)) ? `<button class="change-role-btn" data-user-id="${u.id}" data-current-role="${u.role}" data-new-role="${u.role === 'admin' ? 'user' : 'admin'}">${u.role === 'admin' ? 'Зробити юзером' : 'Зробити адміном'}</button>` : ''}
          </td>
          <td></td>
          <td>
            ${u.pending_avatar_requests && u.pending_avatar_requests.length > 0 ?
              u.pending_avatar_requests.filter(req => req.status === 1).map(req => `
                <div style='margin-bottom:5px;'>
                  <img src='${req.avatar_url || '/static/menu/img/avatar.png'}' style='width:40px;height:40px;border-radius:50%;vertical-align:middle;'>
                  <span>${req.message || ''}</span>
                  <button class="approve-avatar-btn" data-avatar-id="${req.avatar_id}">Схвалити</button>
                  <button class="reject-avatar-btn" data-avatar-id="${req.avatar_id}">Відмовити</button>
                </div>
              `).join('') : '<span style="color:#888">Нет</span>'}
          </td>
        </tr>`).join('')}
    </table>`;
  } catch (e) {
    container.innerHTML = '<p>Ошибка загрузки пользователей</p>';
  }
}
window.loadPermissionsUsers = loadPermissionsUsers;

// Обработчик смены роли (минимально обновляет только ячейку роли)
document.addEventListener('click', async function(e) {
  if (e.target.classList.contains('change-role-btn')) {
    const userId = e.target.dataset.userId;
    const currentRole = e.target.dataset.currentRole;
    const newRole = e.target.dataset.newRole;
    // Здесь можешь добавить confirm или popup, если хочешь подтверждение
    const accessToken = getAuthHeader ? getAuthHeader().Authorization : '';
    const formData = new FormData();
    formData.append('new_role', newRole);
    await fetch(`/users/${userId}/set-role`, {
      method: 'POST',
      headers: { 'Authorization': accessToken },
      body: formData
    });
    // Минимально обновляем только ячейку роли
    const td = e.target.closest('td');
    if (td) {
      if (newRole === 'admin') {
        td.innerHTML = `admin <button class="change-role-btn" data-user-id="${userId}" data-current-role="admin" data-new-role="user">Зробити юзером</button>`;
      } else {
        td.innerHTML = `user <button class="change-role-btn" data-user-id="${userId}" data-current-role="user" data-new-role="admin">Зробити адміном</button>`;
      }
    }
  }
});

// Подтверждение для approve/reject avatar
if (document.addEventListener) {
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('approve-avatar-btn')) {
      const avatarId = e.target.dataset.avatarId;
      showConfirmPopup('Ви впевнені, що хочете схвалити цей аватар як основний?', function() {
        window.approveAvatar && window.approveAvatar(avatarId);
      });
      return;
    }
    if (e.target.classList.contains('reject-avatar-btn')) {
      const avatarId = e.target.dataset.avatarId;
      showConfirmPopup('Ви впевнені, що хочете відмовити у встановленні цього аватара?', function() {
        window.rejectAvatar && window.rejectAvatar(avatarId);
      });
      return;
    }
  });
}

// Універсальна функція показу popup
function showConfirmPopup(message, onYes) {
  // Видалити попередній popup, якщо є
  document.querySelectorAll('.pending-cancel-popup').forEach(e => e.remove());
  const popup = document.createElement('div');
  popup.className = 'pending-cancel-popup';
  popup.innerHTML = `${message}<br><div style='margin-top:8px;display:flex;gap:10px;justify-content:center'><button class='pending-cancel-yes'>Так</button><button class='pending-cancel-no'>Відміна</button></div>`;
  document.body.appendChild(popup);
  popup.querySelector('.pending-cancel-yes').onclick = () => { popup.remove(); onYes(); };
  popup.querySelector('.pending-cancel-no').onclick = () => popup.remove();
}

// Функції для управління кількома обліковими записами
let knownAccounts = [];

// --- Обновление статусов аккаунтов через /auth/accounts/status ---
async function updateAccountStatuses() {
  // Получаем список ID аккаунтов
  const accountIds = knownAccounts.map(account => account.id);
  if (!accountIds.length) return;
  
  try {
    // Запрашиваем статусы через новый эндпоинт
    const response = await fetch(`/auth/accounts/status?user_ids=${accountIds.join(',')}`, {
      method: 'GET',
      headers: {
        ...getAuthHeader()
      },
      credentials: 'include'
    });
    
    if (!response.ok) {
      console.error('Ошибка при получении статусов аккаунтов:', response.statusText);
      return;
    }
    
    const data = await response.json();
    
    // Обновляем статусы в списке аккаунтов
    knownAccounts.forEach(account => {
      if (data[account.id]) {
        // Преобразуем статус API в статус для отображения
        const apiStatus = data[account.id].status;
        if (apiStatus === 'active') {
          account.status = 'active'; // Зеленый - активный (есть refresh_token)
        } else if (apiStatus === 'inactive') {
          account.status = 'inactive'; // Желтый - неактивный (есть access_token, нет refresh_token)
        } else {
          account.status = 'expired'; // Серый - истекший (нет токенов)
        }
      }
    });
    
    // Обновляем отображение
    updateAccountsDropdown();
  } catch (error) {
    console.error('Ошибка при обновлении статусов аккаунтов:', error);
  }
}

// Оновлення випадаючого меню з обліковими записами
function updateAccountsDropdown() {
  const accountsMenu = document.getElementById('accounts-dropdown');
  if (!accountsMenu) return;
  
  // Очищаем меню
  accountsMenu.innerHTML = '';
  
  // Получаем текущего пользователя
  const currentUser = getCurrentUser();
  
  // Добавляем аккаунты
  knownAccounts.forEach(account => {
    const item = document.createElement('div');
    item.className = 'dropdown-item';
    item.dataset.userId = account.id;
    
    // Добавляем иконку статуса с цветом в зависимости от статуса
    const statusIcon = document.createElement('span');
    let statusClass = 'unknown';
    
    // Определяем класс для статуса (цвет точки)
    if (account.status === 'active') {
      statusClass = 'active'; // Зеленый - активный (есть refresh_token)
    } else if (account.status === 'inactive') {
      statusClass = 'inactive'; // Желтый - неактивный (есть access_token, нет refresh_token)
    } else if (account.status === 'expired') {
      statusClass = 'expired'; // Серый - истекший (нет токенов)
    }
    
    statusIcon.className = `status-icon ${statusClass}`;
    item.appendChild(statusIcon);
    
    // Добавляем имя пользователя
    const nameSpan = document.createElement('span');
    nameSpan.textContent = account.username;
    nameSpan.className = 'account-name';
    item.appendChild(nameSpan);
    
    // Добавляем галочку для текущего аккаунта
    if (currentUser && currentUser.id === account.id) {
      const checkmark = document.createElement('span');
      checkmark.className = 'checkmark';
      checkmark.innerHTML = '&#10003;';
      item.appendChild(checkmark);
      item.classList.add('current');
    }
    
    // Добавляем обработчик клика с учетом статуса
    item.addEventListener('click', () => {
      if (account.status === 'active' || account.status === 'inactive') {
        // Для активных и неактивных аккаунтов используем прямое переключение
        switchAccount(account);
      } else {
        // Для истекших аккаунтов перенаправляем на страницу входа
        window.location.href = `/login?email=${encodeURIComponent(account.email)}`;
      }
    });
    
    accountsMenu.appendChild(item);
  });
  
  // Добавляем разделитель и пункт "Выйти"
  if (knownAccounts.length > 0) {
    const divider = document.createElement('div');
    divider.className = 'dropdown-divider';
    accountsMenu.appendChild(divider);
  }
  
  const logoutItem = document.createElement('div');
  logoutItem.className = 'dropdown-item logout';
  logoutItem.textContent = 'Выйти';
  logoutItem.addEventListener('click', () => {
    // Используем новый эндпоинт для выхода
    fetch('/auth/logout', {
      method: 'POST',
      credentials: 'include'
    }).then(() => {
      window.location.href = '/login';
    });
  });
  accountsMenu.appendChild(logoutItem);
  
  // Добавляем стили для точек статуса, если их еще нет
  addStatusStyles();
}

// Добавление стилей для точек статуса
function addStatusStyles() {
  // Проверяем, есть ли уже стили
  if (document.getElementById('account-status-styles')) return;
  
  const styleEl = document.createElement('style');
  styleEl.id = 'account-status-styles';
  styleEl.textContent = `
    .status-icon {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 8px;
    }
    .status-icon.active {
      background-color: #4CAF50; /* Зеленый */
    }
    .status-icon.inactive {
      background-color: #FFC107; /* Желтый */
    }
    .status-icon.expired {
      background-color: #9E9E9E; /* Серый */
    }
    .status-icon.unknown {
      background-color: #E0E0E0; /* Светло-серый */
    }
  `;
  
  document.head.appendChild(styleEl);
}

// Переключення на інший обліковий запис
async function switchAccount(account) {
  try {
    // Используем новый эндпоинт для переключения аккаунтов
    const response = await fetch(`/auth/switch/${account.id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include'
    });
    
    if (!response.ok) {
      console.error('Ошибка при переключении аккаунта:', response.statusText);
      // Если аккаунт истек, перенаправляем на страницу входа
      if (response.status === 401) {
        window.location.href = `/login?email=${encodeURIComponent(account.email)}`;
        return;
      }
      return;
    }
    
    const data = await response.json();
    
    // Перезагружаем страницу или перенаправляем на дашборд
    const username = data.username || account.username;
    const role = data.role || 'user';
    window.location.href = `/${username}_${role}/`;
  } catch (error) {
    console.error('Ошибка при переключении аккаунта:', error);
    // В случае ошибки перенаправляем на старый эндпоинт для совместимости
    window.location.href = `/switch/${account.id}`;
  }
}

// === Обновление статусов аккаунтов ===
async function updateAccountStatuses() {
    if (!knownAccounts.length) return;
    try {
        const userIds = knownAccounts.map(acc => acc.id);
        const fetchFunction = window.authorizedFetch || window.authorizedRequest || fetch;
        const resp = await fetchFunction('/accounts/status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeader()
            },
            body: JSON.stringify(userIds),
            credentials: 'include'
        });
        let statuses = resp;
        // Если fetchFunction возвращает Response, нужно .json()
        if (resp && typeof resp.json === 'function') {
            statuses = await resp.json();
        }
        if (statuses && typeof statuses === 'object') {
            knownAccounts.forEach(acc => {
                acc.status = statuses[acc.id] || 'gray';
            });
            updateAccountsDropdown();
        }
    } catch (e) {
        console.error('Ошибка при обновлении статусов аккаунтов:', e);
    }
}

// === Инициализация при загрузке страницы ===
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        loadKnownAccounts();
        updateAccountStatuses();
    });
} else {
    loadKnownAccounts();
    updateAccountStatuses();
}

document.addEventListener('DOMContentLoaded', function() {
    // Додавання обробника кліку для випадаючого меню
    const accountDropdown = document.querySelector('.account-dropdown');
    if (accountDropdown) {
        accountDropdown.addEventListener('click', function(e) {
            // Перешкоджаємо вспливанню події
            e.stopPropagation();
            
            // Переключаємо видимість випадаючого меню
            const dropdownContent = this.querySelector('.dropdown-content');
            if (dropdownContent) {
                dropdownContent.classList.toggle('show');
            }
        });
    }
    
    // Закриваємо меню при кліку поза ним
    document.addEventListener('click', function() {
        const dropdownContent = document.querySelector('.dropdown-content');
        if (dropdownContent && dropdownContent.classList.contains('show')) {
            dropdownContent.classList.remove('show');
        }
    });
    
    // Завантаження збережених облікових записів з localStorage
    loadKnownAccounts();
    
    // Перевіряємо поточного користувача та додаємо його до списку
    const currentUser = {
        id: window.currentUserId || '',
        username: window.currentUsername || '',
        email: window.currentEmail || '',
        role: window.userRole || 'user'
    };
    
    console.log("Поточний користувач:", currentUser);
    
    // Якщо у нас є дані про поточного користувача, додаємо його до списку відомих облікових записів
    if (currentUser.id && (currentUser.email || currentUser.username)) {
        addToKnownAccounts(currentUser);
    }
    
    // Оновлюємо дропдаун меню
    updateAccountsDropdown();
});

// === Завантаження відомих облікових записів з localStorage ===
function loadKnownAccounts() {
    const savedAccounts = localStorage.getItem('knownAccounts');
    if (savedAccounts) {
        try {
            knownAccounts = JSON.parse(savedAccounts);
            console.log('Завантажені збережені облікові записи:', knownAccounts);
        } catch (e) {
            console.error('Помилка при завантаженні збережених облікових записів:', e);
            knownAccounts = [];
        }
    } else {
        knownAccounts = [];
    }
}

// === Збереження списку облікових записів в localStorage ===
function saveKnownAccounts() {
    localStorage.setItem('knownAccounts', JSON.stringify(knownAccounts));
}

// === Додавання облікового запису до списку відомих ===
function addToKnownAccounts(account) {
    // Перевіряємо, чи є вже такий обліковий запис у списку
    const existingAccountIndex = knownAccounts.findIndex(acc => acc.id === account.id);
    
    if (existingAccountIndex !== -1) {
        // Оновлюємо існуючий обліковий запис
        knownAccounts[existingAccountIndex] = {
            ...knownAccounts[existingAccountIndex],
            ...account
        };
    } else {
        // Додаємо новий обліковий запис
        knownAccounts.push(account);
    }
    
    // Зберігаємо оновлений список
    saveKnownAccounts();
}

// === Оновлення випадаючого меню з обліковими записами ===
function updateAccountsDropdown() {
    const dropdownContent = document.querySelector('.dropdown-content');
    if (!dropdownContent) return;
    dropdownContent.innerHTML = '';

    // Удаляем дубли по id: если среди дублей есть avatar_url — оставляем его, иначе последний
    const uniqueMap = {};
    knownAccounts.forEach(acc => {
        if (!uniqueMap[acc.id]) {
            uniqueMap[acc.id] = acc;
        } else {
            // Если новый вариант содержит avatar_url — используем его
            if ((acc.avatar_url && acc.avatar_url.length > 4) || (acc.main_avatar_url && acc.main_avatar_url.length > 4)) {
                uniqueMap[acc.id] = acc;
            } else if (!(uniqueMap[acc.id].avatar_url && uniqueMap[acc.id].avatar_url.length > 4)) {
                // Если в uniqueMap еще не было avatar_url — обновляем на последний
                uniqueMap[acc.id] = acc;
            }
        }
    });
    let sortedAccounts = Object.values(uniqueMap);
    // Сортируем: текущий аккаунт — первый
    if (window.currentUserId) {
        sortedAccounts.sort((a, b) => (String(a.id) === String(window.currentUserId) ? -1 : String(b.id) === String(window.currentUserId) ? 1 : 0));
    }

    // Фильтрация и подготовка аватарок по ролям
    sortedAccounts.forEach(account => {
        const isCurrentAccount = String(account.id) === String(window.currentUserId);
        let displayName = (account.username || '').substring(0, 8);
        let displayEmail = (account.email || '').substring(0, 8);
        let displayRole = account.role || 'user';

        // --- Логика аватарок ---
        let avatarUrl = '/static/menu/img/avatar.png';
        const isAdmin = window.userRole === 'admin' || window.userRole === 'superadmin';
        if (isAdmin) {
            // Админы и суперадмины видят аватарки всех аккаунтов
            if (account.avatar_url && typeof account.avatar_url === 'string' && account.avatar_url.length > 4) {
                avatarUrl = account.avatar_url;
            }
        } else {
            // Обычные юзеры видят только свою аватарку и "зеленых"
            if (isCurrentAccount || account.status === 'green') {
                if (account.avatar_url && typeof account.avatar_url === 'string' && account.avatar_url.length > 4) {
                    avatarUrl = account.avatar_url;
                }
            }
        }

        const accountItem = document.createElement('div');
        accountItem.className = 'account-item' + (isCurrentAccount ? ' active-account' : '');

        accountItem.innerHTML = `
          <div class="account-grid">
            <div class="avatar-cell">
              <img class="account-avatar" src="${avatarUrl}" alt="avatar">
              <span class="status-dot ${account.status === 'green' ? 'dot-green' : 'dot-gray'}"></span>
              ${isCurrentAccount ? '<span class="checkmark">&#10003;</span>' : ''}
            </div>
            <div class="username-cell">${displayName}</div>
            <div class="email-cell">${displayEmail}</div>
            <div class="role-cell">${displayRole}</div>
          </div>
        `;
        if (!isCurrentAccount) {
            accountItem.addEventListener('click', () => {
                if (account.status === 'green') {
                    switchAccount(account);
                } else {
                    let loginUrl = '/login';
                    if (account.email) {
                        loginUrl += '?email=' + encodeURIComponent(account.email);
                    }
                    window.location.href = loginUrl;
                }
            });
        }
        dropdownContent.appendChild(accountItem);
    });
    // Разделитель и кнопка добавления аккаунта
    if (sortedAccounts.length > 0) {
        const divider = document.createElement('div');
        divider.className = 'dropdown-divider';
        dropdownContent.appendChild(divider);
    }
    const addLoginLink = document.createElement('a');
    addLoginLink.href = '/login';
    addLoginLink.className = 'add-login-link';
    addLoginLink.textContent = 'Додати обліковий запис';
    dropdownContent.appendChild(addLoginLink);
}

// === Переключення на інший обліковий запис ===
function switchAccount(account) {
    // Перешкоджаємо вспливанню події кліку
    event.stopPropagation();
    
    // Тут відправляємо запит на сервер для переключення на вибраний обліковий запис
    window.location.href = `/switch_account/${account.id}`;
}