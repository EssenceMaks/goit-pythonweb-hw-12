// JS для попапів

// Універсальні функції для попапів
function openPopup(id) {
  document.querySelectorAll('.popup').forEach(p => {
    p.style.display = 'none';
    const form = p.querySelector('form');
    if (form) form.reset();
  });
  const popup = document.getElementById(id);
  if (popup) {
    popup.style.display = 'block';
    // Фокус на перше поле
    setTimeout(() => {
      const firstInput = popup.querySelector('input,textarea');
      if (firstInput) firstInput.focus();
    }, 100);
  }
}

function closePopup(id) {
  const popup = document.getElementById(id);
  if (popup) {
    popup.style.display = 'none';
    const form = popup.querySelector('form');
    if (form) form.reset();
    // Очищення динамічних телефонів і груп
    if (document.getElementById('phones-list')) document.getElementById('phones-list').innerHTML = '';
    if (document.getElementById('groups-list')) document.getElementById('groups-list').innerHTML = '';
    if (document.querySelector('[name="groups"]')) document.querySelector('[name="groups"]').value = '';
  }
}

// Динамічні телефони
const phonesListElement = document.getElementById('phones-list');
const phoneAddBtn = document.getElementById('add-phone-btn'); // Переименовали переменную, чтобы избежать конфликта
const phoneTypes = ['Мобільний', 'Домашній', 'Робочий', 'Інший'];
function addPhoneRow(value = '', type = 'Мобільний') {
  if (!phonesListElement) return;
  const idx = phonesListElement.children.length;
  const row = document.createElement('div');
  row.className = 'phone-row';
  // Виправлений pattern для всіх браузерів
  row.innerHTML = `<div class='phone-input-wrap form-field'><input class='phone-input' type='tel' pattern='[0-9()+#* -]{2,31}' minlength='2' maxlength='31' inputmode='tel' value='${value}' placeholder='номер телефону' required><div class='phone-error field-error' data-field='phone_${idx}'></div></div><select class='phone-type'>${phoneTypes.map(t => `<option${t===type?' selected':''}>${t}</option>`).join('')}</select><button type='button' class='remove-phone-btn' title='Видалити'>✕</button>`;
  row.querySelector('.remove-phone-btn').onclick = () => row.remove();
  phonesListElement.appendChild(row);
}
if (phoneAddBtn) { // Используем переименованную переменную
  phoneAddBtn.onclick = () => addPhoneRow();
}

// Кастомна inline-валідація для телефону та інших полів
function showPhoneError(input) {
  const errorDiv = input.parentElement.querySelector('.phone-error, .field-error');
  if (input.validity.valueMissing) {
    errorDiv.textContent = 'Це поле обовʼязкове .. від двох символів 1-9 # * ( )';
  } else if (input.validity.patternMismatch) {
    errorDiv.textContent = 'Заповніть правильно: тільки цифри, +, -, (, ), #, *, пробіли, від 2 до 31 символа';
  } else if (input.validity.tooShort) {
    errorDiv.textContent = 'Мінімум 2 символи';
  } else if (input.validity.tooLong) {
    errorDiv.textContent = 'Максимум 31 символ';
  } else {
    errorDiv.textContent = '';
  }
}

function showCustomFieldError(input) {
  const errorDiv = input.parentElement.querySelector('.field-error');
  if (!errorDiv) return;
  if (input.name === 'first_name' || input.name === 'last_name') {
    if (input.validity.tooLong) {
      errorDiv.textContent = 'Це поле максимум 198 символів';
    } else {
      errorDiv.textContent = '';
    }
  } else if (input.name === 'extra_info') {
    if (input.validity.tooLong) {
      errorDiv.textContent = 'Це поле максимум 500 символів';
    } else {
      errorDiv.textContent = '';
    }
  }
}

document.addEventListener('input', function(e) {
  if (e.target.matches('input[type="tel"]')) {
    e.target.value = e.target.value.replace(/[^0-9+\-()#* ]/g, '');
    showPhoneError(e.target);
  }
  if (e.target.name === 'first_name' || e.target.name === 'last_name' || e.target.name === 'extra_info') {
    showCustomFieldError(e.target);
  }
});
document.addEventListener('blur', function(e) {
  if (e.target.matches('input[type="tel"]')) {
    showPhoneError(e.target);
  }
  if (e.target.name === 'first_name' || e.target.name === 'last_name' || e.target.name === 'extra_info') {
    showCustomFieldError(e.target);
  }
}, true);

// Динамічні групи (UI-заготовка)
const groupsList = document.getElementById('groups-list');
const addGroupBtn = document.getElementById('add-group-btn');
const groupVariants = ['Сімʼя', 'Друзі', 'Робота', 'Спорт', 'Інше'];
function addGroupLabel(name) {
  if (!groupsList) return;
  const label = document.createElement('span');
  label.className = 'group-label';
  label.innerHTML = `${name}<button type='button' class='remove-group-btn' title='Видалити'>✕</button>`;
  label.querySelector('.remove-group-btn').onclick = () => {
    label.remove();
    updateGroupsInput();
  };
  groupsList.appendChild(label);
  updateGroupsInput();
}
function updateGroupsInput() {
  const input = document.querySelector('[name="groups"]');
  if (input && groupsList) {
    input.value = Array.from(groupsList.children).map(l => l.textContent.replace('✕','').trim()).join(', ');
  }
}
if (addGroupBtn) {
  addGroupBtn.onclick = () => {
    // UI: показати дропдаун, поки просто prompt
    const name = prompt('Назва групи', groupVariants[0]);
    if (name && !Array.from(groupsList.children).some(l => l.textContent.includes(name))) {
      addGroupLabel(name);
    }
  };
}

// Аватар-ромб: буква імені
const firstNameInput = document.querySelector('[name="first_name"]');
const avatarLetter = document.getElementById('contact-avatar-letter');
if (firstNameInput && avatarLetter) {
  firstNameInput.addEventListener('input', () => {
    avatarLetter.textContent = (firstNameInput.value[0] || 'A').toUpperCase();
  });
}

// === Обробка помилок форми контакту ===

// Отримання інформації про користувача з сессії
function getUserInfo() {
    // Спочатку пробуємо отримати з sessionStorage
    const session = JSON.parse(sessionStorage.getItem('user') || '{}');
    if (Object.keys(session).length > 0) return session;
    
    // Якщо не знайдено в sessionStorage, пробуємо отримати з cookie
    const cookie = document.cookie.match(/user=([^;]*)/);
    if (cookie) {
        const user = JSON.parse(decodeURIComponent(cookie[1]));
        if (Object.keys(user).length > 0) {
            // Зберігаємо в sessionStorage для подальшого використання
            sessionStorage.setItem('user', JSON.stringify(user));
            return user;
        }
    }
    return null;
}

// Отримання user_id з сессії
function getUserId() {
    const user = getUserInfo();
    return user ? user.id : null;
}

function showFieldError(field, message) {
  const errorDiv = document.querySelector('.field-error[data-field="' + field + '"]');
  if (errorDiv) {
    errorDiv.textContent = message;
    errorDiv.classList.add('active');
    // Підсвітити поле
    const input = document.querySelector('[name="' + field + '"]');
    if (input) input.classList.add('invalid-field');
  }
}
function clearFieldError(field) {
  const errorDiv = document.querySelector('.field-error[data-field="' + field + '"]');
  if (errorDiv) {
    errorDiv.textContent = '';
    errorDiv.classList.remove('active');
    // Прибрати підсвітку
    const input = document.querySelector('[name="' + field + '"]');
    if (input) input.classList.remove('invalid-field');
  }
}
function clearAllFieldErrors() {
  document.querySelectorAll('.field-error').forEach(div => {div.textContent = '';div.classList.remove('active');});
  document.querySelectorAll('.invalid-field').forEach(i => i.classList.remove('invalid-field'));
}
// Очищення помилок при введенні
['input','change'].forEach(evt => {
  document.addEventListener(evt, function(e) {
    if (e.target.name) clearFieldError(e.target.name);
  });
});
// Перехоплення сабміту форми контакту
const contactForm = document.getElementById('create-contact-form');
if (contactForm) {
  contactForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    clearAllFieldErrors();
    // HTML5 валідація
    if (!contactForm.checkValidity()) {
      Array.from(contactForm.elements).forEach(el => {
        if (!el.validity.valid) {
          if (el.type === 'tel') showPhoneError(el);
          else if (el.name === 'first_name' || el.name === 'last_name' || el.name === 'extra_info') showCustomFieldError(el);
          else showFieldError(el.name, el.validationMessage);
        }
      });
      return;
    }
    const formData = new FormData(contactForm);
    // Збираємо телефони
    const phones = Array.from(document.querySelectorAll('.phone-row .phone-input')).map(input => ({number: input.value, type: input.closest('.phone-row').querySelector('.phone-type').value}));
    formData.delete('phones');
    // Збираємо групи
    const groups = document.querySelector('[name="groups"]').value;
    // Формуємо payload
    const payload = Object.fromEntries(formData.entries());
    payload.phone_numbers = phones;
    payload.groups = groups;
    
    // Додаємо user_id та перевіряємо роль користувача
    const user = getUserInfo();
    if (!user) {
        showFieldError('form', 'Необхідна авторизація');
        return;
    }
    
    // Проверяем наличие id
    if (!user.id) {
        showFieldError('form', 'Сессия не содержит user_id');
        return;
    }
    
    // Для супер-адміна та адміна дозволяємо явно задавати user_id
    if (user.role === 'superadmin' || user.role === 'admin') {
        // Якщо не вказано user_id - створюємо для себе
        // Исправление: убираем обращение к несуществующей переменной contact
        payload.user_id = user.id;
    } else if (user.role === 'user') {
        // Для звичайного користувача використовуємо user_id з сессії
        payload.user_id = user.id;
    } else {
        showFieldError('form', 'Немає доступу для створення контакта');
        return;
    }
    try {
      const resp = await fetch(contactForm.action || window.location.pathname, {
        method: contactForm.method || 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (!resp.ok) {
        // Обробка помилок валідації
        if (data.detail) {
          if (Array.isArray(data.detail)) {
            data.detail.forEach(err => {
              const field = err.loc && err.loc.length ? err.loc[err.loc.length-1] : 'form';
              showFieldError(field, err.msg);
            });
          } else {
            showFieldError('form', data.detail);
          }
        }
      } else {
        // Успіх: закрити попап, скинути форму і помилки
        contactForm.reset();
        clearAllFieldErrors();
        closePopup('popup-create-contact');
        // Можна оновити список контактів
      }
    } catch (err) {
      showFieldError('form', 'Помилка мережі, спробуйте ще раз.');
    }
  });
}

window.openPopup = openPopup;
window.closePopup = closePopup;
window.addPhoneRow = addPhoneRow;
window.addGroupLabel = addGroupLabel;
window.updateGroupsInput = updateGroupsInput;
