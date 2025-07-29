document.addEventListener('DOMContentLoaded', function () {
  const btn = document.querySelector('#copyNumber');
  if (!btn || !btn.dataset.number) return;

  btn.addEventListener('click', function () {
    const text = btn.dataset.number;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = '✅ Скопировано!';
        setTimeout(() => { btn.textContent = '📋 Копировать'; }, 1500);
      }).catch(err => {
        console.error('Clipboard error:', err);
        fallbackCopy(text);
      });
    } else {
      fallbackCopy(text);
    }
  });

  function fallbackCopy(text) {
    const temp = document.createElement("textarea");
    temp.value = text;
    document.body.appendChild(temp);
    temp.focus();
    temp.select();
    try {
      document.execCommand("copy");
      btn.textContent = '✅ Скопировано!';
      setTimeout(() => { btn.textContent = '📋 Копировать'; }, 1500);
    } catch (err) {
      alert("Не удалось скопировать номер.");
    }
    document.body.removeChild(temp);
  }
});

// Убираем всплывающие сообщения через 4 сек
setTimeout(function () {
  const alerts = document.querySelectorAll("#flash-container .alert");
  alerts.forEach(function (alert) {
    alert.classList.remove("show");
    alert.classList.add("fade");
    setTimeout(() => alert.remove(), 500);
  });
}, 4000);


// Генерация и вставка пароля при создании пользователя
document.addEventListener("DOMContentLoaded", function () {
  const genBtn = document.getElementById("genPassword");
  const genStatus = document.getElementById("genStatus");
  const passwordField = document.querySelector('input[name="password"]');

  if (genBtn && passwordField) {
    genBtn.addEventListener("click", function () {
      const chars =
        "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%";
      const tempPassword = Array.from(
        { length: 8 },
        () => chars[Math.floor(Math.random() * chars.length)]
      ).join("");

      passwordField.value = tempPassword;
      passwordField.focus();
      passwordField.select();

      navigator.clipboard
        .writeText(tempPassword)
        .then(() => {
          genStatus.style.display = "inline";
          setTimeout(() => {
            genStatus.style.display = "none";
          }, 3000);
        })
        .catch(() => {
          alert("Не удалось скопировать пароль в буфер обмена.");
        });
    });
  }
});


// Переключение типа поля Показать,с= скрыть пароль
document.addEventListener("DOMContentLoaded", function () {
  const toggle = document.getElementById("togglePassword");
  const field = document.getElementById("passwordField");

  if (toggle && field) {
    toggle.addEventListener("click", function () {
      const isHidden = field.getAttribute("type") === "password";
      field.setAttribute("type", isHidden ? "text" : "password");
      toggle.textContent = isHidden ? "🙈 Скрыть" : "👁 Показать";
    });
  }
});


// Контроль включенного капс лока
document.addEventListener("DOMContentLoaded", function () {
  const passwordInput = document.getElementById("passwordField");
  const capsWarning = document.createElement("div");
  capsWarning.className = "text-warning small mt-1";
  capsWarning.textContent = "⚠️ Включён Caps Lock";
  capsWarning.style.display = "none";
  passwordInput.parentNode.appendChild(capsWarning);

  passwordInput.addEventListener("keyup", function (e) {
    const capsOn = e.getModifierState && e.getModifierState("CapsLock");
    capsWarning.style.display = capsOn ? "block" : "none";
  });
});
