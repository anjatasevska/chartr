/* Chartr — shared UI helpers */

const COIN_DETAIL_BASE = "/coins/";
const PAPRIKA_BASE = "https://api.coinpaprika.com/v1";

// Global coin search, available on every page via the header search bar.
window.searchAndRedirect = async function (query) {
  if (!query) return;
  try {
    const url = `${PAPRIKA_BASE}/search?q=${encodeURIComponent(query)}&c=currencies&limit=1`;
    const res = await fetch(url);
    const data = await res.json();
    const first = data.currencies && data.currencies[0];
    if (first) {
      window.location.href = COIN_DETAIL_BASE + first.id + "/";
    } else {
      alert("No coin found with that name or symbol.");
    }
  } catch (err) {
    alert("Error searching for coin. Try again.");
  }
};

document.addEventListener('DOMContentLoaded', () => {
  const menuBtn = document.getElementById('mobileMenuBtn');
  const sidebar = document.querySelector('.sidebar');

  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (window.innerWidth <= 768 &&
          !sidebar.contains(e.target) &&
          !menuBtn.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  const searchInput = document.getElementById('globalSearch');
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const term = e.target.value.trim();
        if (term) {
          window.searchAndRedirect(term);
        }
      }
    });
  }
});
