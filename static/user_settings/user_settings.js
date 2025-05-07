// Файл для роботи з налаштуваннями користувача

document.addEventListener('DOMContentLoaded', function() {
  // Находим ссылку настроек в меню
  const settingsLink = document.querySelector('.settings-link');
  if (settingsLink) {
    settingsLink.addEventListener('click', function(e) {
      e.preventDefault(); // Предотвращаем переход по ссылке
      
      // Тут очистка пошуку потрібна, оскільки це початкова завантаження налаштувань
      const searchInput = document.getElementById('contact-search');
      if (searchInput) {
        // Сохраняем оригинальное значение поиска, чтобы восстановить его при необходимости
        window._savedSearchValue = searchInput.value;
        searchInput.value = '';
        
        // Обновляем URL без параметра поиска
        const currentUrl = new URL(window.location.href);
        if (currentUrl.searchParams.has('search')) {
          currentUrl.searchParams.delete('search');
          history.replaceState({}, '', currentUrl);
        }
      }
      
      renderUserSettings();
    });
  }
});

// Глобальная переменная для хранения данных пользователя
let currentUserData = null;

// Функция для отображения настроек пользователя
async function renderUserSettings() {
  const contactsList = document.getElementById('contacts-list');
  if (!contactsList) return;
  
  // Сбрасываем глобальные состояния (если используются переменные из contacts.js)
  if (typeof birthdayMode !== 'undefined') birthdayMode = false;
  if (typeof expandedContactId !== 'undefined') expandedContactId = null;
  
  try {
    // Получаем информацию о текущем пользователе
    const userData = await authorizedFetch('/users/me');
    console.log('Получены данные пользователя:', userData);
    
    // Если данные о пользователе не загрузились, используем запасные данные из глобальных переменных
    if (!userData) {
      console.warn('Не удалось загрузить данные пользователя из API, используем данные из сессии');
      
      // Используем глобальные переменные, установленные в index.html как запасной вариант
      currentUserData = {
        id: window.currentUserId,
        username: window.currentUsername,
        email: window.currentEmail,
        role: window.userRole
      };
    } else {
      // Сохраняем данные пользователя в глобальную переменную
      currentUserData = userData;
    }
    
    // Создаем шаблон настроек пользователя в стеклянном стиле
    const settingsTemplate = `
      <div class="user-settings-container" id="settings-container">
        <div class="settings-header">
          <button id="back-to-contacts-btn" class="back-btn">← Повернутися до контактів</button>
          <h2>Налаштування користувача</h2>
        </div>
        
        <div class="settings-form">
          <div class="settings-row">
            <div class="settings-label">Email:</div>
            <div class="settings-value">${currentUserData.email || ''}</div>
            <div class="settings-action">
              <span class="email-note">(Змінити неможливо)</span>
            </div>
          </div>
          
          <div class="settings-row" id="username-row">
            <div class="settings-label">Ім'я користувача:</div>
            <div class="settings-value">${currentUserData.username || ''}</div>
            <div class="settings-action">
              <button class="edit-username-btn">Редагувати</button>
            </div>
          </div>
          
          <div class="settings-row" id="password-row">
            <div class="settings-label">Пароль:</div>
            <div class="settings-value">********</div>
            <div class="settings-action">
              <button class="edit-password-btn">Змінити пароль</button>
              <button class="reset-password-btn">Скинути пароль</button>
            </div>
          </div>
          
          <div class="settings-row" id="avatar-row">
            <div class="settings-label">
              Аватар:
              <div class="avatar-preview">
                <img src="${currentUserData.avatar_url || '/static/menu/img/user_1.png'}" alt="Аватар користувача">
              </div>
            </div>
            
            <div class="settings-action">
              <button class="upload-avatar-btn">Додати аватар</button>
              <button class="change-avatar-btn">Змінити аватар</button>
            </div>
            
            <div class="settings-value">
              <div class="user_avatar_cloudinary">
                <!-- Здесь будут отображаться загруженные аватары -->
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Устанавливаем шаблон настроек в блок контактов
    contactsList.innerHTML = settingsTemplate;
    contactsList.setAttribute('data-mode', 'settings');
    
    // Добавляем обработчики событий для кнопок
    setupSettingsEventHandlers();

    // --- Добавляем кнопку Permissions для админов ---
    console.log('Текущая роль пользователя:', currentUserData.role); // Для отладки
    if (currentUserData && ["admin", "superadmin"].includes(currentUserData.role)) {
      const settingsHeader = document.querySelector('.settings-header');
      if (settingsHeader && !document.getElementById('permissions-btn')) {
        const permBtn = document.createElement('button');
        permBtn.id = 'permissions-btn';
        permBtn.className = 'permissions-btn';
        permBtn.innerText = 'Permissions';
        permBtn.style.marginLeft = '20px';
        permBtn.onclick = function() { showPermissionsModal(); };
        settingsHeader.appendChild(permBtn);
      }
    }

    // Предотвращаем сброс страницы при клике внутри контейнера настроек
    const container = document.getElementById('settings-container');
    if (container) {
      container.addEventListener('click', function(e) {
        e.stopPropagation(); // Останавливаем всплытие события
      });
    }
    
 
    
    // Загружаем аватары пользователя (вызываем функцию из user_avatar_settings.js)
    if (typeof window.setupUserAvatars === 'function') {
      window.setupUserAvatars();
    } else if (typeof loadUserAvatars === 'function') {
      loadUserAvatars();
    }
    
  } catch (error) {
    console.error('Ошибка при загрузке данных пользователя:', error);
    contactsList.innerHTML = '<div class="error-message">Помилка при завантаженні налаштувань користувача</div>';
  }
}

// --- Функция для показа окна после сброса пароля ---


function showPasswordResetSent(email) {
  const contactsList = document.getElementById('contacts-list');
  if (!contactsList) return;
  contactsList.innerHTML = `
    <div class="glass-container password-reset-info">
      <h2>Скидання паролю</h2>
      <div class="info-text">
        На вашу електронну пошту <b>${email}</b> надіслано лист для відновлення паролю.<br>
        Перевірте пошту та завершіть процедуру скидання паролю за посиланням у листі.
      </div>
      <div class="login-link" style="margin-top:24px; color:#87f06c;">
        <a href="#" id="logout-and-reset-link" class="login-link" style="color:#87f06c;">Вийти(розлогінитися) для нового логіну</a>
      </div>
    </div>
  `;
  contactsList.setAttribute('data-mode', 'reset-password-info');
}
// Настройка обработчиков событий для кнопок в настройках
function setupSettingsEventHandlers() {
  // Кнопка возврата к контактам - должна быть единственным способом выйти из настроек
  const backBtn = document.getElementById('back-to-contacts-btn');
  if (backBtn) {
    backBtn.addEventListener('click', function() {
      returnToContacts();
    });
  }
  
  // Редактирование имени пользователя
  const editUsernameBtn = document.querySelector('.edit-username-btn');

  // --- Сброс пароля из настроек ---
  const resetPasswordBtn = document.querySelector('.reset-password-btn');
  if (resetPasswordBtn) {
    resetPasswordBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      showPasswordResetConfirmBlock();
    });
  }

// Блок-подтверждение сброса пароля
function showPasswordResetConfirmBlock() {
  const passwordRow = document.getElementById('password-row');
  if (!passwordRow || !currentUserData || !currentUserData.email) return;
  passwordRow.innerHTML = `
    <div class="settings-label">Пароль:</div>
    <div class="settings-value">
      <div class="password-reset-confirm-block">
        <div class="confirm-text">Ви впевнені що хочете вийти і пройти процедуру відновлення пароля?</div>
        <div class="confirm-actions">
          <button id="confirm-reset-password-btn" class="save-btn">Так</button>
          <button id="cancel-reset-password-btn" class="cancel-btn">Ні</button>
        </div>
      </div>
    </div>
  `;
  // Обработчик "Так"
  const confirmBtn = document.getElementById('confirm-reset-password-btn');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      // Передаём email через query или localStorage
      if (window.sessionStorage) {
        sessionStorage.setItem('forgotEmail', currentUserData.email);
      }
      window.location.href = `/forgot?email=${encodeURIComponent(currentUserData.email)}`;
    });
  }
  // Обработчик "Ні"
  const cancelBtn = document.getElementById('cancel-reset-password-btn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      renderUserSettings();
    });
  }
}

  if (editUsernameBtn) {
    editUsernameBtn.addEventListener('click', function(e) {
      e.stopPropagation(); // Предотвращаем всплытие события
      showUsernameEditForm();
    });
  }
  
  // Изменение пароля
  const editPasswordBtn = document.querySelector('.edit-password-btn');
  if (editPasswordBtn) {
    editPasswordBtn.addEventListener('click', function(e) {
      e.stopPropagation(); // Предотвращаем всплытие события
      showPasswordEditForm();
    });
  }
  

  
  // Настраиваем обработчики событий для кнопок аватаров, если функция доступна
  if (typeof window.setupUserAvatars === 'function') {
    console.log('Вызываем функцию настройки аватаров из user_avatar_settings.js');
    window.setupUserAvatars();
  } else {
    console.error('Функция setupUserAvatars не найдена. Проверьте, загружен ли файл user_avatar_settings.js');
    
    // Резервный вариант - добавляем простые обработчики
    const uploadAvatarBtn = document.querySelector('.upload-avatar-btn');
    const changeAvatarBtn = document.querySelector('.change-avatar-btn');
    
    if (uploadAvatarBtn) {
      uploadAvatarBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        alert('Функция загрузки аватара временно недоступна. Пожалуйста, проверьте, что файл user_avatar_settings.js правильно подключен.');
      });
    }
    
    if (changeAvatarBtn) {
      changeAvatarBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        const avatarsContainer = document.querySelector('.user_avatar_cloudinary');
    if (avatarsContainer) {
          avatarsContainer.classList.toggle('show-avatars');
          this.textContent = avatarsContainer.classList.contains('show-avatars') ? 'Сховати аватари' : 'Змінити аватар';
        } else {
          alert('Контейнер для аватаров не найден.');
        }
      });
    }
  }
}

// --- Permissions Modal Logic ---
window.showPermissionsModal = async function() {
  const modal = document.getElementById('permissions-modal');
  const tableContainer = document.getElementById('permissions-table-container');
  if (!modal || !tableContainer) return; // Если элементов нет, ничего не делаем
  modal.style.display = 'block';
  tableContainer.innerHTML = '<div>Завантаження...</div>';
  try {
    const accessToken = getAccessToken ? getAccessToken() : '';
    const resp = await fetch('/users/avatar-requests', {
      headers: { 'Authorization': `Bearer ${accessToken}` }
    });
    if (!resp.ok) throw new Error('Не вдалося отримати заявки');
    const requests = await resp.json();
    if (!requests.length) {
      tableContainer.innerHTML = '<div>Немає заявок</div>';
      return;
    }
    // Получаем id текущего пользователя
    let myId = null;
    if (window.currentUserId) {
      myId = window.currentUserId;
    } else if (window.currentUserData && window.currentUserData.id) {
      myId = window.currentUserData.id;
    } else if (typeof currentUserData === 'object' && currentUserData && currentUserData.id) {
      myId = currentUserData.id;
    }
    let html = `<table class="permissions-table"><thead><tr><th>Avatar</th><th>Username</th><th>Email</th><th>Тип</th><th>Статус</th><th>Дія</th></tr></thead><tbody>`;
    for (const req of requests) {
      html += `<tr>
        <td><img src="${req.avatar_url || '/static/menu/img/avatar.png'}" alt="avatar" style="width:40px;height:40px;border-radius:50%"></td>
        <td>${req.username || ''}</td>
        <td>${req.email || ''}</td>
        <td>${req.request_type || ''}</td>
        <td>${req.status}</td>
        <td>`;
      html += `<button onclick="approveAvatarRequest(${req.avatar_id})">✅</button> <button onclick="rejectAvatarRequest(${req.avatar_id})">❌</button> `;
      // Кнопка смены роли только если это не superadmin и не сам пользователь (строгое сравнение строк)
      if (req.role !== 'superadmin' && String(req.user_id) !== String(myId)) {
        html += `<button class="change-role-btn" data-user-id="${req.user_id}" data-current-role="${req.role}" data-new-role="${req.role === 'admin' ? 'user' : 'admin'}">${req.role === 'admin' ? 'Зробити юзером' : 'Зробити адміном'}</button>`;
      }
      html += `</td></tr>`;
    }
    html += '</tbody></table>';
    tableContainer.innerHTML = html;
  } catch (e) {
    tableContainer.innerHTML = `<div class='error-message'>${e.message}</div>`;
  }
};

window.closePermissionsModal = function() {
  document.getElementById('permissions-modal').style.display = 'none';
};

// --- Модальное подтверждение смены роли ---
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('change-role-btn')) {
    const userId = e.target.dataset.userId;
    const currentRole = e.target.dataset.currentRole;
    const newRole = e.target.dataset.newRole;
    // Открываем красивое модальное окно подтверждения (popup-confirm-change-role)
    const popup = document.getElementById('popup-confirm-change-role');
    if (popup) {
      popup.style.display = 'block';
      document.getElementById('confirm-change-role-message').innerText = newRole === 'admin' ?
        'Ви дійсно хочете змінити роль користувача з юзера на адміна?' :
        'Ви дійсно хочете змінити роль користувача з адміна на юзера?';
      const confirmBtn = document.getElementById('btn-confirm-change-role');
      confirmBtn.dataset.userId = userId;
      confirmBtn.dataset.newRole = newRole;
    }
  }
});

const confirmChangeRoleBtn = document.getElementById('btn-confirm-change-role');
if (confirmChangeRoleBtn) {
  confirmChangeRoleBtn.addEventListener('click', async function() {
    const userId = this.dataset.userId;
    const newRole = this.dataset.newRole;
    const accessToken = getAccessToken ? getAccessToken() : '';
    const formData = new FormData();
    formData.append('new_role', newRole);
    await fetch(`/users/${userId}/set-role`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${accessToken}` },
      body: formData
    });
    document.getElementById('popup-confirm-change-role').style.display = 'none';
    await showPermissionsModal();
  });
}
const cancelChangeRoleBtn = document.getElementById('btn-cancel-change-role');
if (cancelChangeRoleBtn) {
  cancelChangeRoleBtn.addEventListener('click', function() {
    document.getElementById('popup-confirm-change-role').style.display = 'none';
  });
}

// Старый prompt/alert/confirm для смены роли полностью убираем
window.changeUserRole = undefined;

// Функция для отображения формы редактирования имени пользователя
function showUsernameEditForm() {
  const usernameRow = document.getElementById('username-row');
  if (!usernameRow) return;
  
  const currentUsername = currentUserData ? currentUserData.username : '';
  
  // Заменяем содержимое строки на форму редактирования
  usernameRow.innerHTML = `
    <div class="settings-label">Ім'я користувача:</div>
    <div class="settings-value">
      <input type="text" id="new-username" value="${currentUsername}" class="settings-input" autofocus>
    </div>
    <div class="settings-action">
      <button id="save-username-btn" class="save-btn">Підтвердити</button>
      <button id="cancel-username-btn" class="cancel-btn">Відміна</button>
    </div>
  `;
  
  // Добавляем обработчики для новых кнопок
  const saveBtn = document.getElementById('save-username-btn');
  const cancelBtn = document.getElementById('cancel-username-btn');
  const usernameInput = document.getElementById('new-username');
  
  // Предотвращаем сброс при клике на элементы формы
  if (usernameInput) {
    usernameInput.addEventListener('click', function(e) {
      e.stopPropagation();
    });
    
    // Фокусируемся на поле ввода и выделяем текст
    setTimeout(() => {
      usernameInput.focus();
      usernameInput.select();
    }, 0);
    
    // Добавляем обработчик нажатия Enter для сохранения
    usernameInput.addEventListener('keypress', function(e) {
      e.stopPropagation();
      if (e.key === 'Enter') {
        saveUsername();
      }
    });
  }
  
  if (saveBtn) {
    saveBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      saveUsername();
    });
  }
  
  if (cancelBtn) {
    cancelBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      // Отменяем редактирование и восстанавливаем отображение
      renderUserSettings();
    });
  }
}

// Функция для сохранения нового имени пользователя
async function saveUsername() {
  const newUsername = document.getElementById('new-username').value.trim();
  
  if (!newUsername) {
    alert('Ім\'я користувача не може бути порожнім');
    return;
  }
  
  try {
    // Отправляем запрос на изменение имени пользователя
    const response = await authorizedFetch('/users/update/username', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username: newUsername })
    });
    
    // Обновляем глобальную переменную с именем пользователя
    if (typeof window.currentUsername !== 'undefined') {
      window.currentUsername = newUsername;
    }
    if (currentUserData) {
      currentUserData.username = newUsername;
    }
    
    // Обновляем имя пользователя в интерфейсе
    updateDashboardUserProfile();
    
    // Обновляем отображение после успешного изменения
    renderUserSettings();
    
    if (typeof addFooterMessage === 'function') {
      addFooterMessage('Ім\'я користувача успішно оновлено', 'success');
    } else {
      alert('Ім\'я користувача успішно оновлено');
    }
  } catch (error) {
    console.error('Ошибка при обновлении имени пользователя:', error);
    alert('Помилка при оновленні імені користувача');
  }
}

// Функция обновления профиля пользователя в дашборде
function updateDashboardUserProfile() {
  // Обновляем аватар в главном меню
  if (typeof loadUserProfile === 'function') {
    loadUserProfile();
    return;
  }
  
  // Альтернативный способ - обновляем аватар и имя пользователя напрямую
  const menuAvatar = document.querySelector('.avatar-in-menu img');
  const menuUsername = document.querySelector('.username-in-menu');
  
  // Обновляем также имя пользователя в основном блоке меню
  const usernameInMenu = document.querySelector('.username');
  
  if (menuAvatar) {
    const currentAvatar = document.querySelector('.avatar-preview img');
    if (currentAvatar) {
      menuAvatar.src = currentAvatar.src;
    }
  }
  
  if (menuUsername && currentUserData) {
    menuUsername.textContent = currentUserData.username;
  }
  
  if (usernameInMenu && currentUserData) {
    usernameInMenu.textContent = currentUserData.username;
  }
}

// Функция для отображения формы изменения пароля
function showPasswordEditForm() {
  const passwordRow = document.getElementById('password-row');
  if (!passwordRow) return;
  
  // Заменяем содержимое строки на форму редактирования
  passwordRow.innerHTML = `
    <div class="settings-label">Пароль:</div>
    <div class="settings-value">
      <div class="password-edit-form">
        <div class="form-group">
          <label for="current-password">Поточний пароль:</label>
          <input type="password" id="current-password" class="settings-input" required autocomplete="new-password" data-form-type="other" data-lpignore="true">
        </div>
        <div class="form-group">
          <label for="new-password">Новий пароль:</label>
          <input type="password" id="new-password" class="settings-input" required minlength="6" autocomplete="new-password" data-form-type="other" data-lpignore="true">
        </div>
        <div class="form-group">
          <label for="confirm-password">Підтвердіть новий пароль:</label>
          <input type="password" id="confirm-password" class="settings-input" required minlength="6" autocomplete="new-password" data-form-type="other" data-lpignore="true">
        </div>
      </div>
    </div>
    <div class="settings-action password-edit-actions">
      <button id="save-password-btn" class="save-btn">Підтвердити</button>
      <button id="cancel-password-btn" class="cancel-btn">Відміна</button>
    </div>
  `;
  
  // Предотвращаем сброс при клике на элементы формы
  const inputs = passwordRow.querySelectorAll('input');
  inputs.forEach(input => {
    input.addEventListener('click', function(e) {
      e.stopPropagation();
    });
  });
  
  // Фокусируемся на первом поле ввода
  const currentPasswordInput = document.getElementById('current-password');
  if (currentPasswordInput) {
    setTimeout(() => {
      currentPasswordInput.focus();
    }, 0);
  }
  
  // Добавляем обработчики для новых кнопок
  const saveBtn = document.getElementById('save-password-btn');
  const cancelBtn = document.getElementById('cancel-password-btn');
  
  if (saveBtn) {
    saveBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      savePassword();
    });
  }
  
  if (cancelBtn) {
    cancelBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      
      // Отменяем редактирование и восстанавливаем отображение
      renderUserSettings();
    });
  }
}

// Функция для сохранения нового пароля
async function savePassword() {
  const currentPassword = document.getElementById('current-password').value;
  const newPassword = document.getElementById('new-password').value;
  const confirmPassword = document.getElementById('confirm-password').value;
  
  if (!currentPassword || !newPassword || !confirmPassword) {
    alert('Всі поля повинні бути заповнені');
    return;
  }
  
  if (newPassword !== confirmPassword) {
    alert('Новий пароль і підтвердження не співпадають');
    return;
  }
  
  if (newPassword.length < 6) {
    alert('Новий пароль повинен містити не менше 6 символів');
    return;
  }
  
  try {
    // Отправляем запрос на изменение пароля
    const response = await authorizedFetch('/users/update/password', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        current_password: currentPassword,
        new_password: newPassword
      })
    });
    
    // Обновляем отображение после успешного изменения
    renderUserSettings();
    
    // Ждем немного перед показом сообщения
    setTimeout(() => {
      if (typeof addFooterMessage === 'function') {
        addFooterMessage('Пароль успішно змінено', 'success');
      } else {
        alert('Пароль успішно змінено');
      }
    }, 100);
    
  } catch (error) {
    console.error('Ошибка при изменении пароля:', error);
    alert('Помилка при зміні пароля. Можливо, поточний пароль введено невірно.');
  }
}