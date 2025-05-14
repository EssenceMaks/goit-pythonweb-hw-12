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
function addPhoneRow(number = '', label = 'Мобільний') {
  if (!phonesListElement) return;
  const div = document.createElement('div');
  div.className = 'phone-number-row';
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
  div.querySelector('.remove-phone-btn').onclick = () => div.remove();
  phonesListElement.appendChild(div);
}
window.addPhoneRow = addPhoneRow;
if (phoneAddBtn) { // Используем переименованную переменную
  phoneAddBtn.onclick = () => addPhoneRow();
}

// Кастомна inline-валідація для телефону та інших полів
function showPhoneError(input, message) {
    let errorDiv = input.parentElement.querySelector('.phone-error, .field-error');
    if (!errorDiv) return;
    let val = input.value.trim();
    const digits = val.replace(/\D/g, '');
    if(val.length > 0) {
        if (!/^[- 0-9+()#*]{2,32}$/.test(val) || digits.length < 2) {
            errorDiv.textContent = message || 'Мінімум 2 цифри, тільки цифри, + - ( ) # *';
            errorDiv.classList.add('active');
            input.classList.add('input-error');
        } else {
            errorDiv.textContent = '';
            errorDiv.classList.remove('active');
            input.classList.remove('input-error');
        }
    } else {
        errorDiv.textContent = '';
        errorDiv.classList.remove('active');
        input.classList.remove('input-error');
    }
}

function showCustomFieldError(input) {
    let errorDiv = input.parentElement.querySelector('.field-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        input.parentElement.appendChild(errorDiv);
    }
    errorDiv.style.zIndex = '50000';
    let val = input.value.trim();
    if(input.name === 'first_name') {
        if (!val) {
            errorDiv.textContent = 'Введіть ім’я (мінімум 2 символи, тільки букви, цифри і дефіс)';
            errorDiv.classList.add('active');
            input.classList.add('input-error');
        } else if (!/^[-а-яіїєa-z0-9]+$/i.test(val) || val.length < 2) {
            errorDiv.textContent = 'Мінімум 2 символи, тільки букви, цифри і дефіс';
            errorDiv.classList.add('active');
            input.classList.add('input-error');
        } else {
            errorDiv.textContent = '';
            errorDiv.classList.remove('active');
            input.classList.remove('input-error');
        }
        return;
    }
    if (input.validity.valueMissing) {
        errorDiv.textContent = 'Це поле обовʼязкове';
        errorDiv.classList.add('active');
        input.classList.add('input-error');
    } else {
        errorDiv.textContent = '';
        errorDiv.classList.remove('active');
        input.classList.remove('input-error');
    }
}

function clearCustomFieldError(input) {
    let errorDiv = input.parentElement.querySelector('.field-error');
    if (errorDiv) {
        errorDiv.textContent = '';
        errorDiv.classList.remove('active');
    }
    input.classList.remove('input-error');
}

function clearFieldError(field) {
    const input = document.querySelector(`[name="${field}"]`);
    if (!input) return;
    clearCustomFieldError(input);
}

// Добавить novalidate ко всем формам
window.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('form').forEach(form => form.setAttribute('novalidate', 'true'));
});

// Универсальная функция для показа кастомной ошибки над полем
function showCustomFieldError(input, type = null) {
    let errorDiv = input.parentElement.querySelector('.field-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        input.parentElement.appendChild(errorDiv);
    }
    errorDiv.style.zIndex = '50000';
    let val = input.value.trim();
    // always show for first_name, even if not required
    if(input.name === 'first_name') {
        if (!val) {
            errorDiv.textContent = 'Введіть ім’я (мінімум 2 символи, тільки букви, цифри і дефіс)';
            errorDiv.classList.add('active');
            input.classList.add('input-error');
        } else if (!/^[-а-яіїєa-z0-9]+$/i.test(val) || val.length < 2) {
            errorDiv.textContent = 'Мінімум 2 символи, тільки букви, цифри і дефіс';
            errorDiv.classList.add('active');
            input.classList.add('input-error');
        } else {
            errorDiv.textContent = '';
            errorDiv.classList.remove('active');
            input.classList.remove('input-error');
        }
        return;
    }
    // Для других полей
    if (input.validity.valueMissing) {
        errorDiv.textContent = 'Це поле обовʼязкове';
        errorDiv.classList.add('active');
        input.classList.add('input-error');
    } else {
        errorDiv.textContent = '';
        errorDiv.classList.remove('active');
        input.classList.remove('input-error');
    }
}


// Очищать ошибку на ввод


// Валидация: показывать ошибку только на blur, а на input просто очищать
// (чтобы не ругалось при каждом вводе)
document.addEventListener('input', function(e) {
  if (e.target.matches('input,textarea')) {
    clearCustomFieldError(e.target);
  }
});
document.addEventListener('blur', function(e) {
  if (e.target.matches('input,textarea')) {
    if (!e.target.checkValidity()) {
      showCustomFieldError(e.target);
    }
  }
}, true);

// Для телефона — ограничение ввода только разрешёнными символами
// и кастомная ошибка
// (оставляем для совместимости)
document.addEventListener('input', function(e) {
  if (e.target.matches('input[type="tel"]')) {
    const errorDiv = e.target.parentElement.querySelector('.phone-error, .field-error');
    if (errorDiv) errorDiv.textContent = '';
  }
  if (e.target.matches('input[required], input[type="email"], textarea[required]')) {
    clearCustomFieldError(e.target);
  }
});
document.addEventListener('blur', function(e) {
  if (e.target.matches('input[type="tel"]')) {
    showPhoneError(e.target);
  }
  if (e.target.matches('input[required], input[type="email"], textarea[required]')) {
    showCustomFieldError(e.target);
  }
}, true);

// На submit формы — ручная валидация
window.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      let valid = true;
      // Проверяем имя
      const firstName = form.querySelector('[name="first_name"]');
      showCustomFieldError(firstName);
      if (firstName.classList.contains('input-error')) valid = false;
      // Проверяем телефоны
      form.querySelectorAll('input[type="tel"]').forEach(input => {
        showPhoneError(input);
        if (input.classList.contains('input-error')) valid = false;
      });
      // Проверяем остальные обязательные
      form.querySelectorAll('input[required]:not([type="tel"]), input[type="email"], textarea[required]').forEach(input => {
        if (input.name !== 'first_name') {
          if (input.validity.valueMissing) {
            showCustomFieldError(input);
            valid = false;
          }
        }
      });
      if (!valid) return;
      // Отправляем форму
      let data = {};
      form.querySelectorAll('input,textarea,select').forEach(el => {
        data[el.name] = el.value;
      });
      try {
        let fetchOptions = { method: form.method || 'POST' };
        if (fetchOptions.method.toUpperCase() === 'POST' || fetchOptions.method.toUpperCase() === 'PUT' || fetchOptions.method.toUpperCase() === 'PATCH') {
          fetchOptions.headers = { 'Content-Type': 'application/json' };
          fetchOptions.body = JSON.stringify(data);
        }
        const resp = await fetch(form.action || window.location.pathname, fetchOptions);
        if (resp.status === 422) {
          const res = await resp.json();
          if (res.errors) {
            Object.entries(res.errors).forEach(([field, msg]) => {
              showFieldError(field, msg);
            });
          } else if (res.detail) {
            showPopupError(form, res.detail);
          } else {
            showPopupError(form, 'Помилка валідації');
          }
          return;
        }
        if (!resp.ok) {
          const res = await resp.json().catch(() => ({}));
          showPopupError(form, res.detail || 'Помилка');
          return;
        }
        // success, закрываем попап
        closePopup(form.closest('.popup').id);
      } catch (err) {
        showPopupError(form, err.message || 'Помилка');
      }
    });
  });
});


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
    if (input) input.classList.add('input-error');
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
    // Ручная валидация всех обязательных полей
    let firstInvalid = null;
    // first_name
    const firstNameInput = contactForm.querySelector('[name="first_name"]');
    showCustomFieldError(firstNameInput);
    const firstNameError = firstNameInput.parentElement.querySelector('.field-error.active');
    if (firstNameError && firstNameError.textContent) {
      firstInvalid = firstNameInput;
    }
    // email
    const emailInput = contactForm.querySelector('[name="email"]');
    if (emailInput) {
      const val = emailInput.value.trim();
      // Строгая проверка: имя@домен.доменная_зона (зона >=2 буквы)
      const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!val || !emailPattern.test(val)) {
        showFieldError('email', 'Введіть коректний email (наприклад: name@email.com)');
        if (!firstInvalid) firstInvalid = emailInput;
      }
    }
    // birthday
    const birthdayInput = contactForm.querySelector('[name="birthday"]');
    if (birthdayInput) {
      if (!birthdayInput.value.trim()) {
        showFieldError('birthday', 'Виберіть дату народження');
        if (!firstInvalid) firstInvalid = birthdayInput;
      }
    }
    // phones
    const phoneInputs = contactForm.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(phoneInput => {
      let val = phoneInput.value.trim();
      // Проверка: только разрешённые символы и минимум 2 цифры
      const digits = val.replace(/\D/g, '');
      if (val.length > 0) {
        if (!/^[- 0-9+()#*]{2,32}$/.test(val) || digits.length < 2) {
          showPhoneError(phoneInput, digits.length < 2 ? 'Мінімум 2 цифри, тільки цифри, + - ( ) # *' : undefined);
          if (!firstInvalid) firstInvalid = phoneInput;
        } else {
          // если всё ок, убрать ошибку
          showPhoneError(phoneInput, '');
        }
      } else {
        // если пустое, убрать ошибку
        showPhoneError(phoneInput, '');
      }
    });
    if (firstInvalid) {
      firstInvalid.focus();
      return;
    }
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
    let phoneInputsList = document.querySelectorAll('#phones-list input[type="tel"]');
    let phones = Array.from(phoneInputsList)
        .map(input => input.value.trim())
        .filter(val => val.length > 0);
    // Формуємо payload
    const payload = Object.fromEntries(formData.entries());
    payload.phone_numbers = phones;
    // Збираємо групи
    const groups = document.querySelector('[name="groups"]').value;
    payload.groups = groups;
    
    // Валидация поля extra_info
    const extraInfoInput = contactForm.querySelector('[name="extra_info"]');
    if (extraInfoInput && extraInfoInput.value.trim().length > 0) {
      const val = extraInfoInput.value.trim();
      // Проверка длины
      if (val.length > 500) {
        showFieldError('extra_info', 'Не більше 500 символів');
        if (!firstInvalid) firstInvalid = extraInfoInput;
      }
      // Проверка допустимых символов
      if (!/^[-#()а-яА-ЯёЁa-zA-Z0-9 .,!?"'\n]*$/.test(val)) {
        showFieldError('extra_info', 'Дозволені символи: # - ( ) та літери/цифри');
        if (!firstInvalid) firstInvalid = extraInfoInput;
      }
    }

    // Универсальная фильтрация опасных символов для всех текстовых полей
    function sanitizeInput(str) {
      // Удаляем потенциально опасные символы: < > " ' ; --
      return str.replace(/[<>"';]/g, '').replace(/--/g, '');
    }
    // Применяем фильтрацию к основным полям
    [firstNameInput, emailInput, birthdayInput, extraInfoInput].forEach(input => {
      if (input && input.value) input.value = sanitizeInput(input.value);
    });
    phoneInputs.forEach(input => {
      if (input && input.value) input.value = sanitizeInput(input.value);
    });

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

    // --- Обработка ошибок сервера при отправке формы ---
    try {
      // let response = await fetch(...)
      // if (!response.ok) throw response;
      // let data = await response.json();
      // ...
    } catch (err) {
      if (err.status === 422) {
        err.json().then(data => {
          let fieldErrorShown = false;
          Object.entries(data).forEach(([field, errors]) => {
            const input = contactForm.querySelector(`[name="${field}"]`);
            if (input) {
              if (field === 'phone_numbers' || input.type === 'tel') showPhoneError(input, errors.join(' '));
              else showFieldError(field, errors.join(' '));
              if (!fieldErrorShown) {
                input.focus();
                fieldErrorShown = true;
              }
            }
          });
          if (!fieldErrorShown) {
            alert('Заповніть поля вірно');
          }
        });
        return;
      } else {
        alert('Заповніть поля вірно');
      }
    }
    // --- конец блока ---

    // --- Обработка ошибок сервера при отправке формы ---
    // Эта часть должна быть в месте, где отправляется fetch/axios запрос
    // Например, в async submit handler:
    // try { ... } catch (err) {
    //   if (err.response && err.response.status === 422) {
    //     // err.response.data = {field: ["ошибка"]}
    //     Object.entries(err.response.data).forEach(([field, errors]) => {
    //       const input = contactForm.querySelector(`[name="${field}"]`);
    //       if (input) {
    //         showFieldError(field, errors.join(' '));
    //         input.focus();
    //       }
    //     });
    //     return;
    //   } else {
    //     // alert('Глобальная ошибка: ' + err.message);
    //   }
    // }
    // --- конец блока ---

    
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
        // Обработка ошибок валидации (422)
        if (data.detail) {
          if (Array.isArray(data.detail)) {
            data.detail.forEach(err => {
              const field = err.loc && err.loc.length ? err.loc[err.loc.length-1] : 'form';
              // Найти input по имени
              const input = contactForm.querySelector(`[name="${field}"]`);
              if (input) {
                // Найти или создать .field-error
                let errorDiv = input.parentElement.querySelector('.field-error');
                if (!errorDiv) {
                  errorDiv = document.createElement('div');
                  errorDiv.className = 'field-error';
                  input.parentElement.appendChild(errorDiv);
                }
                errorDiv.textContent = err.msg;
                errorDiv.style.display = 'block';
                errorDiv.style.color = '#d32f2f';
                errorDiv.style.marginTop = '4px';
                errorDiv.style.fontSize = '0.95em';
                errorDiv.style.zIndex = '50000';
              } else {
                // Общая ошибка — показать в попапе
                showPopupError(contactForm, err.msg);
              }
            });
          } else {
            showPopupError(contactForm, data.detail);
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
      showPopupError(contactForm, 'Помилка мережі, спробуйте ще раз.');
    }
  });}

// Функция для показа общей ошибки в попапе
function showPopupError(form, msg) {
    // Стараться вставлять popup-error под submit или actions
    let actions = form.querySelector('.popup-actions');
    let errorDiv = form.querySelector('.popup-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'popup-error';
        errorDiv.style.background = '#fff0f0';
        errorDiv.style.color = '#d32f2f';
        errorDiv.style.border = '1px solid #d32f2f';
        errorDiv.style.padding = '8px 12px';
        errorDiv.style.marginTop = '12px';
        errorDiv.style.marginBottom = '0';
        errorDiv.style.borderRadius = '4px';
        errorDiv.style.textAlign = 'center';
        errorDiv.style.zIndex = '50000';
        errorDiv.style.position = 'static';
        if (actions && actions.parentNode) {
            actions.parentNode.insertBefore(errorDiv, actions.nextSibling);
        } else {
            form.prepend(errorDiv);
        }
    }
    errorDiv.textContent = msg;
    errorDiv.style.display = 'block';
    if (errorDiv._timeout) clearTimeout(errorDiv._timeout);
    errorDiv._timeout = setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 3000);
    // Скрывать при любом вводе
    const hide = () => { errorDiv.style.display = 'none'; };
    form.querySelectorAll('input,textarea,select').forEach(el => {
        el.addEventListener('input', hide, { once: true });
        el.addEventListener('focus', hide, { once: true });
    });
}

window.openPopup = openPopup;
window.closePopup = closePopup;
window.addPhoneRow = addPhoneRow;
window.updateGroupsInput = updateGroupsInput;
