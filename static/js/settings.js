document.addEventListener("DOMContentLoaded", function () {
  const openBtn = document.getElementById("openDeleteModal");
  const closeBtn = document.getElementById("closeDeleteModal");
  const confirmBtn = document.getElementById("confirmDelete");

  const modal = document.getElementById("deleteModal");
  const form = document.getElementById("deleteAccountForm");

  if (!openBtn || !closeBtn || !confirmBtn || !modal || !form) return;

  // Open modal
  openBtn.addEventListener("click", function () {
    modal.classList.add("show");
  });

  // Close modal
  closeBtn.addEventListener("click", function () {
    modal.classList.remove("show");
  });

  // Click outside closes modal
  modal.addEventListener("click", function (e) {
    if (e.target === modal) {
      modal.classList.remove("show");
    }
  });

  // Confirm delete → submit form
  confirmBtn.addEventListener("click", function () {
    form.submit();
  });
});