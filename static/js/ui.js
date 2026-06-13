// UI JavaScript helpers

// Sidebar toggle for mobile
function toggleSidebar() {
  const sidebar = document.querySelector('.app-sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar) {
    sidebar.classList.toggle('open');
    if (backdrop) {
      backdrop.classList.toggle('active');
    }
  }
}

function closeSidebar() {
  const sidebar = document.querySelector('.app-sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar) {
    sidebar.classList.remove('open');
  }
  if (backdrop) {
    backdrop.classList.remove('active');
  }
}

// Logout via AJAX (optional fallback to form submission)
function ajaxLogout(event) {
  event.preventDefault();
  fetch(event.target.action, {
    method: 'POST',
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': document.querySelector('input[name=csrfmiddlewaretoken]').value,
    },
    credentials: 'same-origin',
  })
    .then(r => {
      if (r.redirected) {
        window.location.href = r.url;
      } else {
        window.location.reload();
      }
    })
    .catch(err => console.error('Logout failed', err));
}

// Attach handlers when DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('sidebarToggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleSidebar);
  }
  const backdrop = document.getElementById('sidebarBackdrop');
  if (backdrop) {
    backdrop.addEventListener('click', closeSidebar);
  }
  const logoutForm = document.getElementById('logoutForm');
  if (logoutForm) {
    logoutForm.addEventListener('submit', ajaxLogout);
  }
});

// Refresh mailbox listing function
function refreshMailbox(btn) {
  if (btn) {
    btn.classList.add('spinning');
  }
  setTimeout(() => {
    window.location.reload();
  }, 400);
}

