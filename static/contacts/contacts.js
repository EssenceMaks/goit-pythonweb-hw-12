// alert('contacts.js підключено!'); // JS для контактів

// Функція для генерації м'якого випадкового кольору
function getSoftColor(seed) {
  // Проста генерація "м'якого" кольору на основі першої літери
  const colors = [
    '#e0e7ff', '#ffe0ec', '#e0fff4', '#fffbe0', '#e0f7fa', '#f3e0ff', '#eaffd9', '#ffd9e6', '#d9eaff', '#f0fff4'
  ];
  if (!seed) return colors[0];
  const code = seed.charCodeAt(0);
  return colors[code % colors.length];
}

// Функція для генерації м'якого темного кольору
function getSoftDarkColor(seed) {
  // М'які темні кольори
  const colors = [
    '#3e3a5e', // violet haze
    '#4b3f72', // dusky neon purple
    '#5c5270', // lavender smoke
    '#364f6b', // calm tech blue
    '#3b3f58', // matte indigo
    '#6a67ce', // soft neon violet
    '#00c9a7'  // glowing mint
  ];
  
  if (!seed) return colors[0];
  const code = seed.charCodeAt(0);
  return colors[code % colors.length];
}

// --- Island-контакти: collapsed/expanded ---
function collapseAllContacts() {
  document.querySelectorAll('.contact-tile.expanded').forEach(tile => {
    tile.classList.remove('expanded');
    tile.querySelector('.contact-tile-actions').style.display = 'none';
    tile.querySelector('.contact-tile-extra').style.display = 'none';
  });
}

// Универсальный обработчик для раскрытия/сворачивания контакта и выхода из birthdayMode
// Теперь birthdayMode можно сбросить только по клику вне шаблона дней рожденья или по спец. кнопке

document.addEventListener('click', async function(e) {
  // Если активен birthdayMode, разрешаем только клик по .show-info-btn или по кнопке выхода
  if (birthdayMode) {
    if (e.target.classList.contains('show-info-btn')) return;
    if (e.target.classList.contains('exit-birthday-btn')) {
      birthdayMode = false;
      expandedContactId = null;
      document.querySelectorAll('#contacts-views button').forEach(btn => btn.classList.remove('active-birthday-btn'));
      // Используем authorizedFetch для получения данных при выходе из birthdayMode
      await fetchAndRenderContactsInner({search: document.getElementById('contact-search')?.value || '', dir: alphaSortDir});
      return;
    }
    // Клик вне шаблона дней рожденья — выйти из режима
    if (!e.target.closest('#contacts-list')) {
      birthdayMode = false;
      expandedContactId = null;
      document.querySelectorAll('#contacts-views button').forEach(btn => btn.classList.remove('active-birthday-btn'));
      // Используем authorizedFetch для получения данных при выходе из birthdayMode 
      await fetchAndRenderContactsInner({search: document.getElementById('contact-search')?.value || '', dir: alphaSortDir});
      return;
    }
    // Внутри birthdayMode ничего не делаем
    return;
  }
  const tile = e.target.closest('.contact-tile');
  if (!tile) {
    expandedContactId = null;
    renderContacts();
    return;
  }
  const id = tile.dataset.id;
  if (contactsViewMode === 4) return;
  if (expandedContactId === id) {
    expandedContactId = null;
  } else {
    expandedContactId = id;
  }
  renderContacts();
});

// Удалена дублирующая функция renderContactTile (используйте только renderContactTile с viewMode)
// function renderContactTile(contact) {
// ...удалено как дубликат и невалидный остаток...


let contactsViewMode = 2; // Дефолтний режим
let alphaSortDir = 'asc'; // глобальне напрям сортування
let expandedContactId = null; // id индивидуально раскрытого контакта
let birthdayMode = false; // глобальный режим дней рождений
let contactsCache = []; // Глобальный кэш контактов

// --- Перемикач вигляду контактів ---
document.addEventListener('DOMContentLoaded', function() {
  // Храним последнюю нажатую кнопку режима для предотвращения повторных запросов
  let lastClickedBtn = null;
  let lastClickTime = 0;

  document.querySelectorAll('.contacts-view-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
      // Предотвращаем повторные быстрые клики и запросы
      const now = Date.now();
      if (lastClickedBtn === btn && now - lastClickTime < 1000) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      
      lastClickedBtn = btn;
      lastClickTime = now;
      
      // Если мы в режиме просмотра дней рождения, не позволяем переключать режимы просмотра
      if (birthdayMode) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      
      contactsViewMode = +btn.dataset.view;
      
      // Устанавливаем атрибут data-view-mode на контейнере контактов
      const contactsList = document.getElementById('contacts-list');
      if (contactsList) {
        contactsList.setAttribute('data-view-mode', contactsViewMode);
      }
      
      expandedContactId = null;
      const search = document.getElementById('contact-search')?.value.trim() || '';
      fetchAndRenderContactsInner({search, dir: alphaSortDir});
    });
  });

  // Добавить кнопку сортировки (стрелка вверх/вниз), только если её нет
  // Использовать #contacts-views как контейнер для кнопок состояний
  let globalSortBtn = document.getElementById('global-alpha-sort');
  const viewSwitcher = document.getElementById('contacts-views');
  if (viewSwitcher && !globalSortBtn) {
    globalSortBtn = document.createElement('button');
    globalSortBtn.id = 'global-alpha-sort';
    globalSortBtn.title = 'Сортировать по алфавиту';
    globalSortBtn.innerHTML = '<span id="alpha-arrow">\u25B2</span>';
    globalSortBtn.style.marginLeft = '0.5em';
    globalSortBtn.style.fontSize = '1.2em';
    globalSortBtn.style.verticalAlign = 'middle';
    globalSortBtn.addEventListener('click', function(e) {
      // Предотвращаем двойные клики
      const now = Date.now();
      if (now - lastClickTime < 1000) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      
      lastClickTime = now;
      
      alphaSortDir = (alphaSortDir === 'asc' ? 'desc' : 'asc');
      document.getElementById('alpha-arrow').textContent = (alphaSortDir === 'asc' ? '\u25B2' : '\u25BC');
      
      // Если мы в режиме просмотра дней рождения, не делаем запросы контактов
      if (birthdayMode) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      
      expandedContactId = null;
      const search = document.getElementById('contact-search')?.value.trim() || '';
      const url = buildContactsUrl({search, dir: alphaSortDir, birthdayMode: false});
      updateApiLink(url);
      fetchAndRenderContactsInner({search, dir: alphaSortDir});
    });
    viewSwitcher.appendChild(globalSortBtn);
  }
  
  // --- Добавить кнопку 7dayBirthDayS ---
  if (viewSwitcher && !document.getElementById('btn-7day-birthdays')) {
    const birthdayBtn = document.createElement('button');
    birthdayBtn.id = 'btn-7day-birthdays';
    birthdayBtn.textContent = '7dayBirthDayS';
    birthdayBtn.style.marginLeft = '0.5em';
    birthdayBtn.style.fontWeight = 'bold';
    birthdayBtn.addEventListener('click', function(e) {
      // Предотвращаем все возможные формы повторного срабатывания
      e.preventDefault();
      e.stopPropagation();
      
      // Проверка на быстрые клики
      const now = Date.now();
      if (now - lastClickTime < 1000) {
        return;
      }
      lastClickTime = now;
      lastClickedBtn = birthdayBtn;
      
      // Переключаем режим дней рождений
      if (birthdayMode) {
        // Если уже в режиме дней рождений - выключаем его
        birthdayMode = false;
        birthdayBtn.classList.remove('active-birthday-btn');
        // Возвращаемся к обычному отображению контактов
        const search = document.getElementById('contact-search')?.value.trim() || '';
        fetchAndRenderContactsInner({search, dir: alphaSortDir});
      } else {
        // Включаем режим дней рождений
        birthdayMode = true;
        
        // Визуальное выделение
        document.querySelectorAll('#contacts-views button').forEach(btn => btn.classList.remove('active-birthday-btn'));
        birthdayBtn.classList.add('active-birthday-btn');
        
        // Запуск шаблона дней рождений
        fetchAndRenderBirthdaysTemplate();
      }
    });
    viewSwitcher.appendChild(birthdayBtn);
    
    // Добавляем CSS стили для активной кнопки
    const style = document.createElement('style');
    style.textContent = `
      .active-birthday-btn {
        background-color: #6a5acd !important;
        color: white !important;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.3) !important;
      }
    `;
    document.head.appendChild(style);
  }

  // Корректно интегрировать поле поиска внутрь #contacts-views, чтобы оно был первым элементом
  let searchInput = document.getElementById('contact-search');
  if (searchInput) {
    searchInput.remove(); // удалить старое поле, если было
  }
  searchInput = document.createElement('input');
  searchInput.type = 'search'; // Изменил тип с text на search
  searchInput.id = 'contact-search';
  searchInput.className = 'contact-search';
  searchInput.placeholder = 'Пошук...';
  
  // Добавляем специальные атрибуты для предотвращения автозаполнения
  searchInput.setAttribute('autocomplete', 'off');
  searchInput.setAttribute('autocorrect', 'off');
  searchInput.setAttribute('autocapitalize', 'off');
  searchInput.setAttribute('data-lpignore', 'true'); // Игнорирование LastPass
  searchInput.setAttribute('data-form-type', 'search'); // Указываем явно, что это поле поиска
  searchInput.setAttribute('spellcheck', 'false');
  searchInput.setAttribute('aria-label', 'Пошук контактів');
  
  searchInput.style.marginRight = '1em';
  searchInput.style.maxWidth = '180px';
  const viewsBlock = document.getElementById('contacts-views');
  if (viewsBlock) {
    viewsBlock.insertBefore(searchInput, viewsBlock.firstChild);
  } else {
    document.body.insertBefore(searchInput, document.body.firstChild);
  }
  // Новый обработчик поиска
  searchInput.addEventListener('input', function() {
    contactsViewMode = 3;
    // expandedContactIds = []; // удалено как неиспользуемое
    birthdayMode = false;
    const search = searchInput.value.trim();
    fetchAndRenderContactsInner({search, dir: alphaSortDir, birthdayMode: false});
  });
  // Сразу при загрузке показать актуальный url
  setTimeout(() => {
    const search = searchInput.value.trim();
    let url = '/contacts?sort=' + encodeURIComponent(alphaSortDir);
    if (search) url += '&search=' + encodeURIComponent(search);
    const apiLink = document.getElementById('api-link');
    if (apiLink) {
      apiLink.href = url;
      apiLink.textContent = url;
    }
  }, 0);
  // Кнопка копирования и перехода по ссылке
  const copyBtn = document.getElementById('copy-api-link');
  const gotoBtn = document.getElementById('goto-api-link');
  const copySuccess = document.getElementById('copy-success');
  // Получаем apiLink здесь
  const apiLink = document.getElementById('api-link');
  if (copyBtn && apiLink) {
    copyBtn.onclick = function() {
      navigator.clipboard.writeText(apiLink.href).then(() => {
        if (copySuccess) {
          copySuccess.style.display = 'inline';
          setTimeout(() => { copySuccess.style.display = 'none'; }, 1200);
        }
      });
    };
  }
  if (gotoBtn && apiLink) {
    gotoBtn.onclick = function() {
      window.open(apiLink.href, '_blank');
    };
  }
  // Сортування: скинути expandedContactIds для всіх sort-btn
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      // expandedContactIds = []; // удалено как неиспользуемое
      renderContacts();
    });
  });
  const sortSelect = document.getElementById('contacts-sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', function() {
      // expandedContactIds = []; // удалено как неиспользуемое
      renderContacts();
    });
  }
  // При загрузке страницы всегда явно режим 2
  contactsViewMode = 2;
  birthdayMode = false;
  fetchAndRenderContactsInner({search: '', dir: alphaSortDir, birthdayMode: false});
});

async function fetchContacts() {
  const search = document.getElementById('contact-search')?.value || '';
  const params = [];
  if (search) params.push('search=' + encodeURIComponent(search));
  if (alphaSortDir) params.push('sort=' + encodeURIComponent(alphaSortDir));
  
  // Проверяем роль пользователя с дополнительной защитой от undefined
  const userRole = window.userRole || '';
  console.log('Current userRole:', userRole); // Добавляем логирование для отладки
  
  // Определяем, является ли пользователь админом или суперадмином
  const isAdminOrSuper = userRole === 'admin' || userRole === 'superadmin';
  
  // Для обычных пользователей — старый endpoint
  if (!isAdminOrSuper) {
    params.push('limit=100');
    const userId = window.selectedUserId;
    if (userId) params.push('user_id=' + encodeURIComponent(userId));
    const url = '/contacts' + (params.length ? '?' + params.join('&') : '');
    try {
      console.log('Выполняется запрос для обычного пользователя:', url);
      // Используем authorizedFetch для отправки JWT-токена
      return await authorizedFetch(url);
    } catch (error) {
      console.error('Ошибка при запросе контактов для обычного пользователя:', error);
      return [];
    }
  } else {
    // Для админа и супер-админа — новый endpoint
    const url = '/contacts/grouped' + (params.length ? '?' + params.join('&') : '');
    try {
      console.log('Выполняется запрос для админа/суперадмина:', url);
      // Используем authorizedFetch для отправки JWT-токена
      return await authorizedFetch(url);
    } catch (error) {
      console.error('Ошибка при запросе контактов для админа/суперадмина:', error, 'userRole =', userRole);
      // Если запрос к групповому эндпоинту не удался, попробуем обычный эндпоинт как запасной вариант
      try {
        const backupUrl = '/contacts' + (params.length ? '?' + params.join('&') : '');
        console.log('Пробуем запасной URL для админа/суперадмина:', backupUrl);
        return await authorizedFetch(backupUrl);
      } catch (backupError) {
        console.error('Ошибка при запросе к запасному URL:', backupError);
        return [];
      }
    }
  }
}

async function fetchContact(id) {
  const userId = window.selectedUserId || document.body.dataset.userId;
  let url = `/contacts/${id}`;
  if (userId) url += `?user_id=${encodeURIComponent(userId)}`;
  // Используем authorizedFetch для отправки JWT-токена
  return await authorizedFetch(url);
}

async function renderContacts() {
  if (birthdayMode) return; // Не рендерить обычные контакты, если активен шаблон дней рожденья
  const list = document.getElementById('contacts-list');
  
  // Устанавливаем атрибут data-view-mode для контейнера контактов
  list.setAttribute('data-view-mode', contactsViewMode);
  
  list.innerHTML = '<div>Завантаження...</div>';
  const data = contactsCache;

  // Для админа и супер-админа: data — массив пользователей с их контактами
  if (window.userRole === 'admin' || window.userRole === 'superadmin') {
    let html = '';
    if (!Array.isArray(data) || !data.length) {
      html = '<div>Контакти не знайдено</div>';
    } else {
      // Получаем ID текущего пользователя для сравнения
      const currentUserId = window.currentUserId || '';
      
      for (const user of data) {
        // Добавляем кнопку смены роли только для админов и обычных пользователей
        // Но не для суперадминов и не для текущего пользователя
        const userRole = user.role || 'user';
        let roleButtonHtml = '';
        
        // Проверяем, что это не суперадмин и не текущий пользователь
        if (userRole !== 'superadmin' && String(user.id) !== String(currentUserId)) {
          const newRole = userRole === 'admin' ? 'user' : 'admin';
          const btnText = userRole === 'admin' ? 'Зробити просто юзером' : 'Зробити адміном';
          roleButtonHtml = `<button class="change-role-btn" data-user-id="${user.id}" data-current-role="${userRole}" data-new-role="${newRole}">${btnText}</button>`;
        }
        
        html += `<div class="user-contacts-section">
          <div class="user-header">
            <b>${user.username}</b> <span style="color:#b6d5fa">(${user.email}, ${userRole})</span>
            ${roleButtonHtml}
          </div>
          <div class="user-contacts-list">`;
          
        // Проверяем наличие контактов
        if (Array.isArray(user.contacts) && user.contacts.length) {
          // Правильное отображение контактов в зависимости от выбранного режима просмотра
          if (contactsViewMode === 4) {
            // Для режима viewMode 4 используем функцию renderFullContactTile
            html += user.contacts.map(contact => renderFullContactTile(contact)).join('');
          } else {
            // Для других режимов обрабатываем каждый контакт
            const contactsHtml = [];
            
            for (const contact of user.contacts) {
              // Проверяем, является ли контакт раскрытым
              if (expandedContactId && contact.id.toString() === expandedContactId) {
                // Если контакт раскрыт, получаем его полные данные и рендерим в расширенном виде
                try {
                  const userId = user.id;
                  let url = `/contacts/${contact.id}`;
                  if (userId) url += `?user_id=${encodeURIComponent(userId)}`;
                  const fullContact = await authorizedFetch(url);
                  contactsHtml.push(renderFullContactTile(fullContact));
                } catch (error) {
                  console.error('Ошибка при загрузке полных данных контакта:', error);
                  contactsHtml.push(renderContactTile(contact, contactsViewMode));
                }
              } else {
                // Если контакт не раскрыт, рендерим его в обычном виде
                contactsHtml.push(renderContactTile(contact, contactsViewMode));
              }
            }
            
            html += contactsHtml.join('');
          }
        } else {
          html += '<div style="margin-left:1em;opacity:0.7">— Контактів немає —</div>';
        }
        
        html += `</div>
        </div><hr style="margin:14px 0;opacity:0.2">`;
      }
    }
    list.innerHTML = html;
    return;
  }

  // Для обычных пользователей — как раньше
  let tilesHtml;
  if (contactsViewMode === 4) {
    tilesHtml = data.map(contact => renderFullContactTile(contact));
  } else {
    tilesHtml = await Promise.all(data.map(async contact => {
      if (expandedContactId && contact.id.toString() === expandedContactId) {
        const fullContact = await fetchContact(contact.id);
        return renderFullContactTile(fullContact);
      } else {
        return renderContactTile(contact, contactsViewMode);
      }
    }));
  }
  list.innerHTML = tilesHtml.join('');
}


// --- Обновление api-link-block ---
function updateApiLink(url) {
  const apiLink = document.getElementById('api-link');
  if (apiLink) {
    apiLink.href = url;
    apiLink.textContent = url;
  }
}

function fetchAndRenderBirthdaysTemplate() {
  birthdayMode = true;
  expandedContactId = null;
  const contactsList = document.getElementById('contacts-list');
  let html = '';
  updateApiLink('/contacts/birthdays/next7days');
  
  // Для админов и суперадминов используем специальный эндпоинт с группировкой по пользователям
  if (window.userRole === 'admin' || window.userRole === 'superadmin') {
    authorizedFetch('/contacts/grouped/birthdays')
      .then(usersWithBirthdays => {
        if (!Array.isArray(usersWithBirthdays) || usersWithBirthdays.length === 0) {
          html = '<div style="margin:1em 0;">Контактів з днями народження не знайдено</div>';
          contactsList.innerHTML = html;
          return;
        }
        
        // Проходим по каждому пользователю и обрабатываем его контакты с днями рождения
        usersWithBirthdays.forEach(user => {
          // Добавляем заголовок пользователя
          const userHeader = `<div class="user-birthday-header">
            <h3>${user.username}</h3>
            <div class="user-info"><span style="color:#b6d5fa">${user.email} (${user.role || 'user'})</span></div>
          </div>`;
          
          html += userHeader;
          
          // Проверяем наличие контактов с днями рождения в ближайшие 7 дней
          const next7DaysContacts = user.contacts_next7days || [];
          
          if (next7DaysContacts.length > 0) {
            html += '<div class="birthday-section"><b>Найближчі 7 днів Дні Народження будуть у:</b></div>';
            html += '<ul>' + next7DaysContacts.map(c => 
              `<li>${c.first_name} ${c.last_name || ''} (${c.birthday || ''}) 
                <button class="show-info-btn" data-id="${c.id}" data-user-id="${user.id}">інфо</button>
              </li>`
            ).join('') + '</ul>';
          } else {
            html += '<div class="birthday-section">У найближчі 7 днів днів народження немає</div>';
          }
          
          // Проверяем наличие контактов с днями рождения в ближайшие 12 месяцев
          const next12MonthsContacts = user.contacts_next12months || [];
          
          if (next12MonthsContacts.length > 0) {
            html += '<div class="birthday-section"><b>Наступні найближчі Дні Народженя:</b></div>';
            
            // Группируем контакты по месяцам
            const months = {};
            next12MonthsContacts.forEach(c => {
              if (!c.birthday) return;
              const m = (new Date(c.birthday)).toLocaleString('uk-UA', {month: 'long'});
              if (!months[m]) months[m] = [];
              months[m].push(c);
            });
            
            Object.keys(months).forEach(month => {
              html += `<div style="margin-top:0.5em;"><b>${month}:</b></div>`;
              html += '<ul>' + months[month].map(c => 
                `<li>${c.first_name} ${c.last_name || ''} (${c.birthday || ''}) 
                  <button class="show-info-btn" data-id="${c.id}" data-user-id="${user.id}">інфо</button>
                </li>`
              ).join('') + '</ul>';
            });
          } else {
            html += '<div class="birthday-section">Немає інших контактів з днями народження</div>';
          }
          
          // Добавляем разделитель между пользователями
          html += '<hr style="margin:14px 0;opacity:0.2">';
        });
        
        contactsList.innerHTML = html;
        
        // Добавляем обработчики для кнопок информации о контакте
        contactsList.querySelectorAll('.show-info-btn').forEach(btn => {
          btn.addEventListener('click', e => {
            const id = btn.getAttribute('data-id');
            const userId = btn.getAttribute('data-user-id');
            if (typeof openFullContactPopup === 'function') {
              openFullContactPopup(id, userId);
            }
            updateApiLink(`/contacts/${id}${userId ? `?user_id=${userId}` : ''}`);
          });
        });
      })
      .catch(error => {
        contactsList.innerHTML = '<div style="color:red">Помилка завантаження Днів Народження</div>';
        console.error('Ошибка при загрузке дней рождения:', error);
      });
  } else {
    // Для обычных пользователей оставляем текущую логику
    authorizedFetch('/contacts/birthdays/next7days')
      .then(data7 => {
        html += '<div><b>Найближчі 7 днів Дні Народження будуть у:</b></div>';
        if (!Array.isArray(data7) || data7.length === 0) {
          html += '<div style="margin:1em 0;">контактів не знайдено</div>';
        } else {
          html += '<ul>' + data7.map(c => `<li>${c.first_name} ${c.last_name || ''} (${c.birthday || ''}) <button class="show-info-btn" data-id="${c.id}">інфо</button></li>`).join('') + '</ul>';
        }
        html += '<hr style="margin:1em 0;">';
        html += '<div><b>Наступні найближчі Дні Народженя:</b></div>';
        
        return authorizedFetch('/contacts/birthdays/next12months');
      })
      .then(data12 => {
        if (Array.isArray(data12) && data12.length > 0) {
          const months = {};
          data12.forEach(c => {
            if (!c.birthday) return;
            const m = (new Date(c.birthday)).toLocaleString('uk-UA', {month: 'long'});
            if (!months[m]) months[m] = [];
            months[m].push(c);
          });
          Object.keys(months).forEach(month => {
            html += `<div style="margin-top:1em;"><b>${month}:</b></div>`;
            html += '<ul>' + months[month].map(c => `<li>${c.first_name} ${c.last_name || ''} (${c.birthday || ''}) <button class="show-info-btn" data-id="${c.id}">інфо</button></li>`).join('') + '</ul>';
          });
        } else {
          html += '<div style="margin:1em 0;">немає контактів</div>';
        }
        contactsList.innerHTML = html;
        contactsList.querySelectorAll('.show-info-btn').forEach(btn => {
          btn.addEventListener('click', e => {
            const id = btn.getAttribute('data-id');
            if (typeof openFullContactPopup === 'function') openFullContactPopup(id);
            updateApiLink(`/contacts/${id}`);
          });
        });
      })
      .catch(error => {
        contactsList.innerHTML = '<div style="color:red">Помилка завантаження Днів Народження</div>';
        console.error('Ошибка при загрузке дней рождения:', error);
      });
  }
}

async function fetchAndRenderContactsInner({birthdayMode: localBirthdayMode = false, search = '', dir = 'asc'} = {}) {
  // Если активен birthdayMode — не перерисовываем список контактов
  if (localBirthdayMode) {
    // --- Только birthday-шаблон! ---
    let html = '';
    updateApiLink('/contacts/birthdays/next7days');
    authorizedFetch('/contacts/birthdays/next7days')
      .then(data7 => {
        html += '<div><b>Найближчі 7 днів Дні Народження будуть у:</b></div>';
        if (!Array.isArray(data7) || data7.length === 0) {
          html += '<div style="margin:1em 0;">контактів не знайдено</div>';
        } else {
          html += '<ul>' + data7.map(c => `<li>${c.first_name} ${c.last_name || ''} (${c.birthday || ''}) <button class="show-info-btn" data-id="${c.id}">інфо</button></li>`).join('') + '</ul>';
        }
        html += '<hr style="margin:1em 0;">';
        html += '<div><b>Наступні найближчі Дні Народженя:</b></div>';
        return authorizedFetch('/contacts/birthdays/next12months');
      })
      .then(data12 => {
        if (Array.isArray(data12) && data12.length > 0) {
          const months = {};
          data12.forEach(c => {
            if (!c.birthday) return;
            const m = (new Date(c.birthday)).toLocaleString('uk-UA', {month: 'long'});
            if (!months[m]) months[m] = [];
            months[m].push(c);
          });
          Object.keys(months).forEach(month => {
            html += `<div style="margin-top:1em;"><b>${month}:</b></div>`;
            html += '<ul>' + months[month].map(c => `<li>${c.first_name} ${c.last_name || ''} (${c.birthday || ''}) <button class="show-info-btn" data-id="${c.id}">інфо</button></li>`).join('') + '</ul>';
          });
        } else {
          html += '<div style="margin:1em 0;">немає контактів</div>';
        }
        contactsList.innerHTML = html;
        contactsList.querySelectorAll('.show-info-btn').forEach(btn => {
          btn.addEventListener('click', e => {
            const id = btn.getAttribute('data-id');
            if (typeof openFullContactPopup === 'function') openFullContactPopup(id);
            updateApiLink(`/contacts/${id}`);
          });
        });
      })
      .catch(() => {
        contactsList.innerHTML = '<div style="color:red">Помилка завантаження найближчих Днів Народження</div>';
      });
  }
  // --- Обычный рендер если НЕ birthdayMode ---
  let url = buildContactsUrl({search, dir, birthdayMode: false, birthdayType: undefined});
  updateApiLink(url);
  const data = await fetchContacts();
  contactsCache = data;
  renderContacts();
}

// --- Обновление api-link-block ---
function updateApiLink(url) {
  const apiLink = document.getElementById('api-link');
  if (apiLink) {
    apiLink.href = url;
    apiLink.textContent = url;
  }
}

function buildContactsUrl({search, dir, birthdayMode, birthdayType}) {
  let url = '/contacts';
  const params = [];
  if (birthdayMode) {
    url = birthdayType === 'next12months' ? '/contacts/birthdays/next12months' : '/contacts/birthdays/next7days';
  } else {
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (dir) params.push(`sort=${dir}`);
    if (params.length) url += '?' + params.join('&');
  }
  return url;
}

function renderContactTile(contact, viewMode) {
  // viewMode: 1, 2, 3
  const firstLetter = contact.first_name ? contact.first_name[0].toUpperCase() : '?';
  if (viewMode === 1) {
    // Только инициалы
    return `<div class="contact-tile contact-tile-mini" data-id="${contact.id}" title="${contact.first_name} ${contact.last_name||''}">
      <div class="contact-avatar-diamond"><span>${firstLetter}${contact.last_name ? contact.last_name[0].toUpperCase() : ''}</span></div>
    </div>`;
  }
  if (viewMode === 2) {
    // Инициалы + имя/фамилия
    return `<div class="contact-tile contact-tile-mini" data-id="${contact.id}">
      <div class="contact-avatar-diamond"><span>${firstLetter}${contact.last_name ? contact.last_name[0].toUpperCase() : ''}</span></div>
      <div class="contact-tile-info">
        <div class="contact-tile-name">${contact.first_name||''}</div>
        <div class="contact-tile-name">${contact.last_name||''}</div>
      </div>
    </div>`;
  }
  if (viewMode === 3) {
    // Имя, фамилия, дата, email, первый телефон
    return `<div class="contact-tile" data-id="${contact.id}">
      <div class="contact-avatar-diamond"><span>${firstLetter}${contact.last_name ? contact.last_name[0].toUpperCase() : ''}</span></div>
      <div class="contact-tile-info">
        <div class="contact-tile-name">${contact.first_name} ${contact.last_name || ''}</div>
        <div class="contact-tile-birth">${contact.birthday || ''}</div>
        <div class="contact-tile-email">${contact.email || ''}</div>
        <div class="contact-tile-phone">${Array.isArray(contact.phone_numbers) && contact.phone_numbers.length ? (contact.phone_numbers[0].number || contact.phone_numbers[0]) : '-'}</div>
      </div>
    </div>`;
  }
  return '';
}

// expanded (4) — полный рендер для плитки в общем списке
function renderFullContactTile(contact) {
  // Почти как renderFullContact, но без отдельного шаблона
  // В режиме 4 добавляем action-кнопки для каждой карточки
  return `<div class="contact-tile contact-tile-expanded" data-id="${contact.id}">
    <div class="contact-avatar-diamond"><span>${contact.first_name ? contact.first_name[0].toUpperCase() : '?'}${contact.last_name ? contact.last_name[0].toUpperCase() : ''}</span></div>
    <div class="contact-tile-info">
      <div class="contact-tile-name">${contact.first_name} ${contact.last_name || ''}</div>
      <div class="contact-tile-birth">${contact.birthday || ''}</div>
      <div class="contact-tile-email">${contact.email || ''}</div>
      <div class="contact-tile-phone">${Array.isArray(contact.phone_numbers) && contact.phone_numbers.length ? contact.phone_numbers.map(pn => `${pn.number} (${pn.label||pn.type||''})`).join(', ') : '-'}</div>
      <div class="contact-tile-groups">${Array.isArray(contact.groups) && contact.groups.length ? contact.groups.map(gr => gr.name || gr).join(', ') : '-'}</div>
      <div class="contact-tile-extra-info">${contact.extra_info || ''}</div>
      <div class="contact-tile-id">ID: ${contact.id}</div>
      <div class="contact-tile-actions" style="display:flex;margin-top:8px;gap:7px;">
        <button class="details-contact" data-id="${contact.id}">Інформація</button>
        <button class="edit-contact" data-id="${contact.id}">Редагувати</button>
        <button class="delete-contact" data-id="${contact.id}">Видалити</button>
      </div>
    </div>
  </div>`;
}

// --- Клик по плитке: трансформация в expanded (4) или возврат в глобальное состояние ---
document.addEventListener('click', function(e) {
  // Если режим дней рождений, не обрабатываем клики по карточкам
  if (birthdayMode) return;
  
  // Находим ближайший элемент .contact-tile (карточку)
  const tile = e.target.closest('.contact-tile');
  if (!tile) return;
  
  // Получаем id контакта из атрибута data-id
  const id = tile.dataset.id;
  if (!id) return;
  
  // В режиме 4 контакты уже полностью развернуты
  if (contactsViewMode === 4) return;
  
  // Переключаем состояние карточки - одинаково для всех пользователей
  if (expandedContactId === id) {
    expandedContactId = null;
  } else {
    expandedContactId = id;
  }
  
  // Перерисовываем контакты, чтобы применить изменения
  renderContacts();
});

// --- кінець island-контактів ---

// Деталі контакту (SPA-стиль)
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.details-contact');
  if (btn) {
    const id = btn.getAttribute('data-id');
    if (id) {
      openFullContactPopup(id);
    }
  }
});

function openFullContactPopup(id) {
  // Используем authorizedFetch вместо fetch
  authorizedFetch(`/contacts/${id}`)
    .then(contact => {
      document.getElementById('popup-full-contact-content').innerHTML = renderFullContact(contact);
      openPopup('popup-full-contact');
    })
    .catch(error => {
      console.error('Ошибка при загрузке контакта:', error);
      alert('Не удалось загрузить контакт. Пожалуйста, попробуйте снова.');
    });
}

// Блокування фону при відкритому попапі
function setPopupOpen(open) {
  document.body.classList.toggle('popup-open', open);
}

const origOpenPopup = window.openPopup;
window.openPopup = function(id) {
  origOpenPopup.call(this, id);
  setPopupOpen(true);
};
const origClosePopup = window.closePopup;
window.closePopup = function(id) {
  origClosePopup.call(this, id);
  setPopupOpen(false);
};

document.querySelectorAll('.popup').forEach(popup => {
  popup.addEventListener('mousedown', function(e) {
    if (e.target === popup) {
      if (confirm('Вийти з редагування контакту?')) {
        closePopup(popup.id);
      }
    }
  });
});

// Відмалювання однієї плитки контакту
function renderFullContact(contact) {
  return `
    <div class="full-contact-card">
      <button id="btn-back-to-list">← Назад</button>
      <h2>${contact.first_name} ${contact.last_name || ''}</h2>
      <div><b>Email:</b> ${contact.email}</div>
      <div><b>День народження:</b> ${contact.birthday || ''}</div>
      <div><b>Телефони:</b> ${Array.isArray(contact.phone_numbers) && contact.phone_numbers.length ? contact.phone_numbers.map(pn => `${pn.number} (${pn.label||pn.type||''})`).join(', ') : '-'}</div>
      <div><b>Групи:</b> ${Array.isArray(contact.groups) && contact.groups.length ? contact.groups.map(gr => gr.name || gr).join(', ') : '-'}</div>
      <div><b>Додатково:</b> ${contact.extra_info || '-'}</div>
      <div><b>ID:</b> ${contact.id}</div>
    </div>
  `;
}

// Делегування подій для редагування і видалення
const contactList = document.getElementById('contacts-list');
if (contactList) {
  contactList.addEventListener('click', async function(e) {
    const btn = e.target.closest('button');
    if (!btn) return;
    const id = btn.getAttribute('data-id');
    if (btn.classList.contains('edit-contact')) {
      openEditContactPopup(id);
    } else if (btn.classList.contains('delete-contact')) {
      document.getElementById('btn-confirm-delete').setAttribute('data-id', id);
      openPopup('popup-confirm-delete');
    }
  });
}

// Відкрити попап і заповнити форму із затримкою для гарантії DOM
async function openEditContactPopup(id) {
  openPopup('popup-create-contact');
  // Чекаємо 100ms, щоб DOM точно був готовий
  setTimeout(async () => {
    const userId = window.selectedUserId || document.body.dataset.userId;
    let url = `/contacts/${id}`;
    if (userId) url += `?user_id=${encodeURIComponent(userId)}`;
    const resp = await authorizedFetch(url);
    const contact = await resp;
    fillContactForm(contact);
    const popupH2 = document.querySelector('#popup-create-contact h2');
    if (popupH2) popupH2.innerText = 'Редагувати контакт';
    createForm.setAttribute('data-edit-id', id);
  }, 100);
}

// Шаблон для відображення повних даних контакту
function showFullContact(contact) {
  const list = document.getElementById('contacts-list');
  list.innerHTML = renderFullContact(contact);
  // Добавить обработчик на кнопку назад
  const btnBack = document.getElementById('btn-back-to-list');
  if (btnBack) {
    btnBack.onclick = () => loadContacts();
  }
}

// Функція для заповнення форми контакту (редагування)
function fillContactForm(contact) {
  console.log('fillContactForm data:', contact);
  createForm.reset();
  createForm.removeAttribute('data-edit-id');
  createForm.first_name.value = contact.first_name || '';
  console.log('first_name value:', createForm.first_name.value);
  createForm.last_name.value = contact.last_name || '';
  console.log('last_name value:', createForm.last_name.value);
  createForm.email.value = contact.email || '';
  console.log('email value:', createForm.email.value);
  createForm.birthday.value = contact.birthday ? contact.birthday.slice(0,10) : '';
  console.log('birthday value:', createForm.birthday.value);
  // Телефоны
  const phonesList = document.getElementById('phones-list');
  if (phonesList) {
    phonesList.innerHTML = '';
    let phones = contact.phone_numbers;
    if (typeof phones === 'string') {
      phones = phones.split(',').map(s => ({number: s.trim(), label: 'Мобільний'})).filter(p => p.number);
    }
    if (!Array.isArray(phones) || !phones.length) phones = [{number: '', label: 'Мобільний'}];
    phones.forEach(pn => {
      if (typeof pn === 'string') pn = {number: pn, label: 'Мобільний'};
      addPhoneRow(pn.number || '', pn.label || pn.type || 'Мобільний');
    });
  }
  // Группы
  const groupsList = document.getElementById('groups-list');
  if (groupsList) {
    groupsList.innerHTML = '';
    let groups = contact.groups;
    if (typeof groups === 'string') groups = groups.split(',').map(g=>g.trim()).filter(Boolean);
    if (!Array.isArray(groups)) groups = [];
    groups.forEach(gr => {
      if (typeof window.addGroupLabel === 'function') {
        window.addGroupLabel(gr);
      }
    });
    if (typeof window.updateGroupsInput === 'function') window.updateGroupsInput();
  }
  createForm.extra_info.value = contact.extra_info || '';
  console.log('extra_info value:', createForm.extra_info.value);
  const popupH2 = document.querySelector('#popup-create-contact h2');
  if (popupH2) popupH2.innerText = 'Редактировать контакт';
}
window.fillContactForm = fillContactForm;

// Динамічне додавання номера телефону
function addPhoneRow(number = '', label = 'Мобільний') {
  const phonesList = document.getElementById('phones-list');
  if (!phonesList) return;
  const div = document.createElement('div');
  div.className = 'phone-number-row';
  // Исправленный pattern: экранирование дефиса и пробела
  div.innerHTML = `
    <div class="phone-input-wrap">
      <input type="tel" required minlength="2" maxlength="32" placeholder="Номер телефону" value="${number}">
      <select>
        <option value="Мобільний"${label==='Мобільний'?' selected':''}>Мобільний</option>
        <option value="Домашній"${label==='Домашній'?' selected':''}>Домашній</option>
        <option value="Робочий"${label==='Робочий'?' selected':''}>Робочий</option>
        <option value="Інший"${label==='Інший'?' selected':''}>Інший</option>
      </select>
      <button type="button" class="remove-phone-btn">✕</button>
    </div>
  `;
  phonesList.appendChild(div);
  div.querySelector('.remove-phone-btn').onclick = () => div.remove();
}
window.addPhoneRow = addPhoneRow;

// Кастомна inline-валідація для телефону
function showPhoneError(input) {
  const errorDiv = input.parentElement.querySelector('.phone-error');
  if (!errorDiv) return;
  if (input.validity.patternMismatch) {
    errorDiv.textContent = 'Заповніть правильно: тільки цифри, +, -, (, ), пробіли';
  } else if (input.validity.valueMissing) {
    errorDiv.textContent = 'Це поле обовʼязкове';
  } else {
    errorDiv.textContent = '';
  }
}
document.addEventListener('input', function(e) {
  if (e.target.matches('input[type="tel"]')) {
    e.target.setCustomValidity('');
    showPhoneError(e.target);
  }
});
document.addEventListener('blur', function(e) {
  if (e.target.matches('input[type="tel"]')) {
    showPhoneError(e.target);
  }
}, true);

// Додавання номера за кнопкою
const addPhoneBtn = document.getElementById('add-phone-btn');
if (addPhoneBtn) {
  addPhoneBtn.onclick = () => addPhoneRow();
}
// При открытии формы всегда хотя бы одно поле телефона
const phonesList = document.getElementById('phones-list');
if (phonesList && phonesList.children.length === 0) {
  addPhoneRow();
}

// При відкритті форми за замовчуванням хоча б один номер
if (window.createForm) {
  window.createForm.addEventListener('reset', () => {
    setTimeout(() => {
      const phonesList = document.getElementById('phones-list');
      if (phonesList) {
        phonesList.innerHTML = '';
        addPhoneRow();
      }
    }, 10);
  });
}

// Створення контакту через форму
const createForm = document.getElementById('create-contact-form');
if (createForm) {
  // Лічильник спроб для дати народження
  let birthdayAttempts = 0;

  createForm.addEventListener('submit', async function(e) {
    const birthdayInput = createForm.birthday;
    if (!birthdayInput.value) {
      birthdayAttempts++;
      if (birthdayAttempts < 3) {
        e.preventDefault();
        birthdayInput.setCustomValidity('Вкажіть дату народження!');
        birthdayInput.reportValidity();
        setTimeout(() => birthdayInput.setCustomValidity(''), 2000);
        return;
      } else {
        birthdayInput.value = '2022-11-06';
        birthdayAttempts = 0;
      }
    } else {
      birthdayAttempts = 0;
    }

    // Перевірка валідності всієї форми
    if (!createForm.checkValidity()) {
      e.preventDefault();
      // Всі помилки будуть показані inline
      return;
    }

    e.preventDefault();
    const formData = new FormData(createForm);
    const data = {};
    for (const [key, value] of formData.entries()) {
      data[key] = value;
    }
    // Збираємо телефони як масив об'єктів {number, label}
    const phoneRows = document.querySelectorAll('#phones-list .phone-number-row');
    data.phone_numbers = [];
    phoneRows.forEach(row => {
      const numberInput = row.querySelector('input[type="tel"]');
      const labelSelect = row.querySelector('select');
      const number = numberInput ? numberInput.value.trim() : '';
      const label = labelSelect ? labelSelect.value : 'Мобільний';
      if (number) {
        data.phone_numbers.push({ number, label });
      }
    });
    // Якщо немає жодного номера, все одно відправляємо порожній масив
    if (!Array.isArray(data.phone_numbers)) data.phone_numbers = [];
    const editId = createForm.getAttribute('data-edit-id');
    let url = '/contacts/';
    let method = 'POST';
    if (editId) {
      url = `/contacts/${editId}`;
      method = 'PUT';
    }
    const userId = window.selectedUserId || document.body.dataset.userId;
    if (userId) {
      data.user_id = userId;
    }
    try {
      // Используем authorizedFetch вместо fetch
      const resp = await authorizedFetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      
      closePopup('popup-create-contact');
      createForm.reset();
      createForm.removeAttribute('data-edit-id');
      const popupH2 = document.querySelector('#popup-create-contact h2');
      if (popupH2) popupH2.innerText = 'Создать контакт';
      window.resetContactsUI();
      window.fetchAndRenderContacts();
    } catch (e) {
      alert('Ошибка: ' + (e.message || 'Не удалось сохранить контакт'));
    }
  });
}

// Підтвердження видалення
const btnDelete = document.getElementById('btn-confirm-delete');
if (btnDelete) {
  btnDelete.addEventListener('click', async function() {
    const id = btnDelete.getAttribute('data-id');
    if (!id) return;
    try {
      const userId = window.selectedUserId;
      let url = `/contacts/${id}`;
      if (userId) url += `?user_id=${encodeURIComponent(userId)}`;
      
      // Используем authorizedFetch вместо fetch
      await authorizedFetch(url, { 
        method: 'DELETE' 
      });
      
      closePopup('popup-confirm-delete');
      window.resetContactsUI();
      window.fetchAndRenderContacts();
      
      // Получить новое количество контактов
      try {
        const data = await authorizedFetch('/db/check-state');
        if (typeof addFooterMessage === 'function') {
          addFooterMessage(`Контакт удалён. Теперь в базе ${data.count} контактов.`, 'success');
        }
      } catch (e) {
        console.error('Ошибка при получении статистики:', e);
      }
    } catch (e) {
      alert('Ошибка при удалении контакта: ' + e.message);
    }
  });
}

// --- API link copy & goto logic + динамічне оновлення ---
function updateApiLink(link) {
  const apiLink = document.getElementById('api-link');
  if (apiLink) {
    apiLink.setAttribute('href', link);
    apiLink.textContent = link;
  }
}

// Для режиму перегляду окремого контакту
function showApiLinkForContact(id) {
  updateApiLink(`/contacts/${id}`);
}

// Для загального списку, пошуку, сортування, днів народження
function showApiLinkForList({search, dir, birthdayMode, birthdayType}) {
  let link = '/contacts';
  const params = [];
  if (birthdayMode) {
    link = birthdayType === 'next12months' ? '/contacts/birthdays/next12months' : '/contacts/birthdays/next7days';
  } else {
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (dir) params.push(`sort=${dir}`);
    if (params.length) link += '?' + params.join('&');
  }
  updateApiLink(link);
}

// Виправляємо формування url для fetch
function buildContactsUrl({search, dir, birthdayMode, birthdayType}) {
  let url = '/contacts';
  const params = [];
  if (birthdayMode) {
    url = birthdayType === 'next12months' ? '/contacts/birthdays/next12months' : '/contacts/birthdays/next7days';
  } else {
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (dir) params.push(`sort=${dir}`);
    if (params.length) url += '?' + params.join('&');
  }
  return url;
}

// --- UI: пошук і сортування контактів ---
document.addEventListener('DOMContentLoaded', function() {
  console.log('Контакты JS загружен');
  const searchInput = document.getElementById('contact-search');
  const sortAlphaBtn = document.getElementById('sort-alpha');
  const sortBirthdayBtn = document.getElementById('sort-birthday');
  const globalSortBtn = document.getElementById('global-alpha-sort');

  let currentSearch = '';
  // birthdayMode, contactsCache, alphaSortDir — глобальные

  // Сбросить поиск и сортировку при инициализации
  if (searchInput) searchInput.value = '';
  if (sortAlphaBtn) sortAlphaBtn.textContent = 'Алфавітний порядок ↑';
  currentSearch = '';
  alphaSortDir = 'asc';
  birthdayMode = false;

  async function fetchAndRenderContactsInnerUI({search = ''} = {}) {
    if (birthdayMode) return;
    let url = '/contacts?sort=' + encodeURIComponent(alphaSortDir);
    if (search) url += '&search=' + encodeURIComponent(search);
    updateApiLink(url);
    const data = await fetchContacts();
    contactsCache = data;
    renderContacts();
  }

  if (searchInput) {
    searchInput.addEventListener('input', e => {
      if (birthdayMode) return;
      currentSearch = e.target.value.trim();
      fetchAndRenderContactsInnerUI({search: currentSearch});
    });
  }

  // Удалён старый обработчик sortAlphaBtn для сортировки (перенесено на делегирование)

  // Глобальная кнопка сортировки (стрелка рядом с режимами)
  // Удалён старый обработчик globalSortBtn для сортировки (перенесено на делегирование)

  if (sortBirthdayBtn) {
    sortBirthdayBtn.addEventListener('click', () => {
      birthdayMode = true;
      if (typeof fetchAndRenderBirthdaysTemplate === 'function') {
        fetchAndRenderBirthdaysTemplate();
      }
      showApiLinkForList({search: currentSearch, dir: alphaSortDir, birthdayMode, birthdayType: 'next7days'});
    });
  }

  // Изначально загрузить контакты
  fetchAndRenderContactsInnerUI({search: currentSearch});
});

// --- кінець UI: пошук і сортування контактів ---

// --- API link copy & goto logic ---

document.addEventListener('DOMContentLoaded', function() {
  const apiLink = document.getElementById('api-link');
  const copyBtn = document.getElementById('copy-api-link');
  const gotoBtn = document.getElementById('goto-api-link');
  const copySuccess = document.getElementById('copy-success');
  if (copyBtn && apiLink) {
    copyBtn.addEventListener('click', () => {
      const url = window.location.origin + apiLink.getAttribute('href');
      navigator.clipboard.writeText(url).then(() => {
        if (copySuccess) {
          copySuccess.style.display = 'inline';
          setTimeout(() => { copySuccess.style.display = 'none'; }, 1200);
        }
      });
    });
  }
  if (gotoBtn && apiLink) {
    gotoBtn.addEventListener('click', () => {
      const url = apiLink.href;
      window.open(url, '_blank');
    });
  }
});

// --- конец API link copy & goto logic ---

document.addEventListener('click', function(e) {
  const btn = e.target.closest('.details-contact, .show-info-btn');
  if (btn) {
    const id = btn.getAttribute('data-id');
    if (id) showApiLinkForContact(id);
  }
});

// Функция сброса и обновления контактов для групповых операций
function resetContactsUI() {
  console.log('Сброс UI контактов');
  // Сбросить состояние UI
  contactsViewMode = 2;
  expandedContactId = null;
  birthdayMode = false;
  
  // Очистить поле поиска
  const searchInput = document.getElementById('contact-search');
  if (searchInput) searchInput.value = '';
  
  // Снять выделение с кнопок дней рождения
  document.querySelectorAll('#contacts-views button').forEach(btn => btn.classList.remove('active-birthday-btn'));
}

// Функция для загрузки и отображения контактов после групповых операций
async function fetchAndRenderContacts() {
  await fetchAndRenderContactsInner();
}

// Обработчик события для кнопок смены роли пользователя
document.addEventListener('click', function(e) {
  const changeRoleBtn = e.target.closest('.change-role-btn');
  if (changeRoleBtn) {
    const userId = changeRoleBtn.dataset.userId;
    const currentRole = changeRoleBtn.dataset.currentRole;
    const newRole = changeRoleBtn.dataset.newRole;
    
    const message = currentRole === 'admin' 
      ? 'Ви дійсно хочете змінити роль користувача з адміна на юзера?'
      : 'Ви дійсно хочете змінити роль користувача з юзера на адміна?';
    
    // Устанавливаем текст сообщения в попапе
    const messageElement = document.getElementById('confirm-change-role-message');
    if (messageElement) {
      messageElement.textContent = message;
    }
    
    // Сохраняем данные для обработчика подтверждения
    const confirmBtn = document.getElementById('btn-confirm-change-role');
    if (confirmBtn) {
      confirmBtn.dataset.userId = userId;
      confirmBtn.dataset.newRole = newRole;
    }
    
    // Отображаем попап для подтверждения
    openPopup('popup-confirm-change-role');
  }
});

// Обработчик события для кнопки подтверждения изменения роли
document.addEventListener('DOMContentLoaded', function() {
  const confirmChangeRoleBtn = document.getElementById('btn-confirm-change-role');
  if (confirmChangeRoleBtn) {
    confirmChangeRoleBtn.addEventListener('click', async function() {
      const userId = this.dataset.userId;
      const newRole = this.dataset.newRole;
      
      if (!userId || !newRole) {
        console.error('Отсутствуют обязательные данные для изменения роли');
        return;
      }
      
      try {
        // Отправляем запрос на изменение роли пользователя
        const response = await authorizedFetch(`/users/${userId}/change-role`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ role: newRole })
        });
        
        // Закрываем попап
        closePopup('popup-confirm-change-role');
        
        // Выводим сообщение об успешном изменении роли
        if (typeof addFooterMessage === 'function') {
          addFooterMessage(`Роль користувача успішно змінена на "${newRole}"`, 'success');
        } else {
          alert(`Роль користувача успішно змінена на "${newRole}"`);
        }
        
        // Обновляем список контактов для отображения актуальных данных
        window.resetContactsUI();
        window.fetchAndRenderContacts();
        
      } catch (error) {
        console.error('Ошибка при изменении роли пользователя:', error);
        if (typeof addFooterMessage === 'function') {
          addFooterMessage('Помилка при зміні ролі користувача', 'error');
        } else {
          alert('Помилка при зміні ролі користувача');
        }
      }
    });
  }
});

// Экспортируем функции для использования в других модулях
window.resetContactsUI = resetContactsUI;
window.fetchAndRenderContacts = fetchAndRenderContacts;
