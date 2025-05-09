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
  
  // Токен может быть уже с префиксом "Bearer " или без него
  const tokenValue = tokenMatch[1];
  if (tokenValue.startsWith('Bearer ')) {
    return {'Authorization': tokenValue};
  } else {
    return {'Authorization': `Bearer ${tokenValue}`};
  }
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
    
    if (!response.ok) {
      console.error(`Ошибка запроса ${url}:`, response.statusText);
      return null;
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Ошибка при запросе ${url}:`, error);
    return null;
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

// Ініціалізація при завантаженні сторінки
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

// Завантаження відомих облікових записів з localStorage
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

// Збереження списку облікових записів в localStorage
function saveKnownAccounts() {
    localStorage.setItem('knownAccounts', JSON.stringify(knownAccounts));
}

// Додавання облікового запису до списку відомих
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

// Оновлення випадаючого меню з обліковими записами
function updateAccountsDropdown() {
    const dropdownContent = document.querySelector('.dropdown-content');
    if (!dropdownContent) return;
    
    // Очищаємо поточне вміст
    dropdownContent.innerHTML = '';
    
    console.log('Оновлення випадаючого меню облікових записів:', knownAccounts);
    
    // Додаємо кожен відомий обліковий запис
    knownAccounts.forEach(account => {
        // Перевіряємо наявність ID для порівняння
        const isCurrentAccount = account.id === window.currentUserId;
        
        // Обрізаємо довгий email до 15 символів та додаємо крапку з комою
        let displayName = account.email || account.username || 'Неизвестный пользователь';
        if (displayName.length > 15) {
            displayName = displayName.substring(0, 15) + '...';
        }
        
        const accountItem = document.createElement('div');
        accountItem.className = 'account-item' + (isCurrentAccount ? ' active-account' : '');
        accountItem.innerHTML = `
            <div class="account-info">
                <div class="account-name">${displayName}</div>
                <div class="account-role">${account.role || 'user'}</div>
            </div>
            ${isCurrentAccount ? '<div class="current-marker">✓</div>' : ''}
        `;
        
        // Додаємо обробник кліку для переключення на цей обліковий запис
        if (!isCurrentAccount) {
            accountItem.addEventListener('click', () => switchAccount(account));
        }
        
        dropdownContent.appendChild(accountItem);
    });
    
    // Додаємо розділювач, якщо є якісь облікові записи
    if (knownAccounts.length > 0) {
        const divider = document.createElement('div');
        divider.className = 'dropdown-divider';
        dropdownContent.appendChild(divider);
    }
    
    // Додаємо кнопку "Add Login"
    const addLoginLink = document.createElement('a');
    addLoginLink.href = '/login';
    addLoginLink.className = 'add-login-link';
    addLoginLink.textContent = 'Додати обліковий запис';
    dropdownContent.appendChild(addLoginLink);
}

// Переключення на інший обліковий запис
function switchAccount(account) {
    // Перешкоджаємо вспливанню події кліку
    event.stopPropagation();
    
    // Тут відправляємо запит на сервер для переключення на вибраний обліковий запис
    window.location.href = `/switch_account/${account.id}`;
}
