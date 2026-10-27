/* Sidebar: a collapsible rail on desktop, an off-canvas drawer on small screens. */
(function () {
  "use strict";

  const shell = document.querySelector("#shell");
  const sidebar = document.querySelector("#sidebar");
  const toggle = document.querySelector("#nav-toggle");
  const scrim = document.querySelector("#scrim");
  const narrow = window.matchMedia("(max-width: 900px)");
  const storageKey = "sidebar-closed";

  if (!shell || !toggle) return;

  function store(closed) {
    try {
      sessionStorage.setItem(storageKey, closed ? "1" : "0");
    } catch (_error) {
      /* The choice still applies to this page view. */
    }
  }

  function stored() {
    try {
      return sessionStorage.getItem(storageKey) === "1";
    } catch (_error) {
      return false;
    }
  }

  function setDrawer(open) {
    shell.classList.toggle("is-drawer", open);
    document.body.classList.toggle("is-locked", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      const first = sidebar.querySelector("a, button");
      if (first) first.focus();
    }
  }

  function setCollapsed(closed) {
    shell.classList.toggle("is-collapsed", closed);
    toggle.setAttribute("aria-expanded", closed ? "false" : "true");
    store(closed);
  }

  function applyMode() {
    if (narrow.matches) {
      shell.classList.remove("is-collapsed");
      setDrawer(false);
    } else {
      shell.classList.remove("is-drawer");
      document.body.classList.remove("is-locked");
      setCollapsed(stored());
    }
  }

  toggle.addEventListener("click", () => {
    if (narrow.matches) setDrawer(!shell.classList.contains("is-drawer"));
    else setCollapsed(!shell.classList.contains("is-collapsed"));
  });

  if (scrim) scrim.addEventListener("click", () => setDrawer(false));

  sidebar.addEventListener("click", (event) => {
    if (narrow.matches && event.target.closest("a")) setDrawer(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && shell.classList.contains("is-drawer")) setDrawer(false);
  });

  if (narrow.addEventListener) narrow.addEventListener("change", applyMode);
  else narrow.addListener(applyMode);

  applyMode();
})();
