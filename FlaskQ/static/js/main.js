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

