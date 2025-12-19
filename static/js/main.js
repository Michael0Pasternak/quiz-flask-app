// Пока пусто. Можно добавить UX (например подсветку выбранного ответа) позже.
console.log("QuizService loaded");
document.getElementById('btnClosePreview').addEventListener('click', () => modal.hidden = true);
// закрытие по клику по фону
document.getElementById('previewBackdrop').addEventListener('click', () => {
  modal.hidden = true;
});

// закрытие по Esc
document.addEventListener('keydown', (e) => {
  if (!modal.hidden && e.key === 'Escape') modal.hidden = true;
});

// ==========================
// QUIZ PASS PAGE SCRIPT
// ==========================
(function () {
  // запускаем только на странице прохождения
  const cards = Array.from(document.querySelectorAll('.quiz-question'));
  if (!cards.length) return;

  const data = window.QUIZ_PASS || {};
  const TOTAL_TIME = Number(data.totalTime) || 90;

  const total = cards.length;
  let idx = 0;

  const counterEl = document.getElementById('qCounter');
  const qBarEl = document.getElementById('progressBar');      // прогресс вопросов
  const timeBarEl = document.getElementById('timeProgress');  // прогресс времени
  const submitBtn = document.getElementById('submitBtn');

  const timerEl = document.getElementById('timerValue');
  const formEl = document.getElementById('quizForm');
  const durationInput = document.getElementById('duration_seconds');

  if (!counterEl || !qBarEl || !timerEl || !formEl) return;

  let timeLeft = TOTAL_TIME;
  const startedAt = Date.now();

  function formatTime(s) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  }

  function updateTimeUI() {
    timerEl.textContent = formatTime(timeLeft);

    if (timeBarEl) {
      const percent = Math.max(0, (timeLeft / TOTAL_TIME) * 100);
      timeBarEl.style.width = percent + '%';

      // краснеет на последних 30%
      if (percent <= 30) {
        timeBarEl.style.background = 'linear-gradient(90deg, #ff4d4d, #ff7a7a)';
      }
    }
  }

  function finishAndSubmit() {
    const elapsed = Math.round((Date.now() - startedAt) / 1000);
    if (durationInput) durationInput.value = elapsed;
    formEl.submit();
  }

  function tick() {
    updateTimeUI();

    if (timeLeft <= 0) {
      finishAndSubmit();
      return;
    }

    timeLeft -= 1;
    setTimeout(tick, 1000);
  }

  function show(i) {
    idx = Math.max(0, Math.min(total - 1, i));
    cards.forEach((c, k) => c.classList.toggle('active', k === idx));

    counterEl.textContent = `Вопрос ${idx + 1}/${total}`;

    // прогресс по вопросам
    qBarEl.style.width = `${Math.round(((idx) / (total - 1 || 1)) * 100)}%`;

    checkSubmitState();
  }

  function currentAnswered() {
    const active = cards[idx];
    return !!active.querySelector('input.answer-radio:checked');
  }

  function checkSubmitState() {
    if (!submitBtn) return;
    submitBtn.disabled = !currentAnswered();
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;

    const action = btn.getAttribute('data-action');
    if (action === 'prev') show(idx - 1);
    if (action === 'next') show(idx + 1);
  });

  document.querySelectorAll('input.answer-radio').forEach(r => {
    r.addEventListener('change', () => {
      if (idx < total - 1) show(idx + 1);
      checkSubmitState();
    });
  });

  // при ручной отправке тоже запишем duration_seconds
  formEl.addEventListener('submit', () => {
    const elapsed = Math.round((Date.now() - startedAt) / 1000);
    if (durationInput) durationInput.value = elapsed;
  });

  show(0);
  tick();
})();
const formEl = document.getElementById('quizForm');
const durationInput = document.getElementById('duration_seconds');
const startedAt = Date.now();

function setDuration(){
  if (!durationInput) return;
  const elapsed = Math.round((Date.now() - startedAt) / 1000);
  durationInput.value = elapsed;
}

// если авто-отправка (время вышло)
function finishAndSubmit(){
  setDuration();
  formEl.submit();
}

// если обычная отправка кнопкой
formEl.addEventListener('submit', () => {
  setDuration();
});
