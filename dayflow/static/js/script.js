// DayFlow HRMS — shared front-end behavior

document.addEventListener("DOMContentLoaded", function () {
  // Mobile sidebar toggle
  const toggleBtn = document.querySelector(".mobile-toggle");
  const sidebar = document.querySelector(".sidebar");
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
  }

  // Auto-dismiss toasts after 4.5s
  document.querySelectorAll(".toast").forEach(function (toast) {
    setTimeout(function () {
      toast.style.transition = "opacity 0.4s ease";
      toast.style.opacity = "0";
      setTimeout(function () { toast.remove(); }, 400);
    }, 4500);
  });

  // Generic modal open/close via data attributes
  document.querySelectorAll("[data-modal-target]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const modal = document.querySelector(btn.getAttribute("data-modal-target"));
      if (modal) modal.classList.add("open");
    });
  });
  document.querySelectorAll("[data-modal-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const overlay = btn.closest(".modal-overlay");
      if (overlay) overlay.classList.remove("open");
    });
  });
  document.querySelectorAll(".modal-overlay").forEach(function (overlay) {
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) overlay.classList.remove("open");
    });
  });

  // Confirm before destructive actions
  document.querySelectorAll("[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      const msg = form.getAttribute("data-confirm") || "Are you sure?";
      if (!window.confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  // Live client-side search filter for simple tables (data-search-target)
  document.querySelectorAll("[data-live-search]").forEach(function (input) {
    input.addEventListener("input", function () {
      const targetSelector = input.getAttribute("data-live-search");
      const rows = document.querySelectorAll(targetSelector + " tbody tr");
      const term = input.value.trim().toLowerCase();
      rows.forEach(function (row) {
        row.style.display = row.textContent.toLowerCase().includes(term) ? "" : "none";
      });
    });
  });

  // Dark / Light mode toggle — persisted in localStorage so it survives refresh & navigation.
  function applyThemeIcon() {
    const btn = document.getElementById("themeToggleBtn");
    if (!btn) return;
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    btn.textContent = isDark ? "☀️" : "🌙";
  }
  applyThemeIcon();
  const themeBtn = document.getElementById("themeToggleBtn");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      const root = document.documentElement;
      const isDark = root.getAttribute("data-theme") === "dark";
      if (isDark) {
        root.removeAttribute("data-theme");
        localStorage.setItem("dayflow-theme", "light");
      } else {
        root.setAttribute("data-theme", "dark");
        localStorage.setItem("dayflow-theme", "dark");
      }
      applyThemeIcon();
    });
  }
});
