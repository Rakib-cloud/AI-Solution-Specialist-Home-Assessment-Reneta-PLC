/* Shared interface helpers: SVG icons, confirm modal, toasts, formatting. */
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";

  const PATHS = {
    eye: ["M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12z", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"],
    pencil: ["M12 20h8", "M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5z"],
    download: ["M12 4v10", "M8 10l4 4 4-4", "M5 20h14"],
    chat: ["M6.5 6h11A1.5 1.5 0 0 1 19 7.5v6A1.5 1.5 0 0 1 17.5 15H9l-3.2 2.6V7.5A1.5 1.5 0 0 1 7.3 6z", "M9.5 10.5h5"],
    check: ["M5 12.5l4.2 4.2L19 7"],
    trash: ["M4 7h16", "M9 7V5h6v2", "M7 7l1 13h8l1-13", "M11 11v6", "M14 11v6"],
    doc: ["M8 3.5h5.5L18 8v11.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19.5V5A1.5 1.5 0 0 1 7.5 3.5", "M13 3.8V8.5h4.6", "M9 13h6", "M9 16.5h4"],
    search: ["M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z", "M15.4 15.4L20 20"],
    upload: ["M12 16V5", "M8 9l4-4 4 4", "M5 19h14"],
    alert: ["M12 8.5v5", "M12 16.6v.4", "M10.3 4.3L2.9 17.2A1.6 1.6 0 0 0 4.3 19.6h15.4a1.6 1.6 0 0 0 1.4-2.4L13.7 4.3a1.6 1.6 0 0 0-2.8 0z"],
    sparkle: ["M12 4.5l1.6 4.2 4.2 1.6-4.2 1.6L12 16.1l-1.6-4.2L6.2 10.3l4.2-1.6z", "M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"],
    bot: ["M7.2 9.6h9.6a2.4 2.4 0 0 1 2.4 2.4v4.4a2.4 2.4 0 0 1-2.4 2.4H7.2a2.4 2.4 0 0 1-2.4-2.4V12a2.4 2.4 0 0 1 2.4-2.4z", "M12 6.6v3", "M12 3.9a1.35 1.35 0 1 0 0 2.7 1.35 1.35 0 0 0 0-2.7z", "M9.6 13.4v1.4", "M14.4 13.4v1.4"],
    user: ["M12 11.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z", "M5.5 20c.6-3.4 3.3-5.5 6.5-5.5s5.9 2.1 6.5 5.5"],
    info: ["M12 11v6", "M12 7.6v.4", "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z"],
    arrowDown: ["M12 5v14", "M6 13l6 6 6-6"],
    send: ["M5 12l15-7-7 15-2.2-5.8z", "M10.8 14.2L20 5"],
    plus: ["M12 5v14", "M5 12h14"],
    copy: ["M9 9h9a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 1 18 21H9a1.5 1.5 0 0 1-1.5-1.5v-9A1.5 1.5 0 0 1 9 9z", "M15.5 6.5v-1A1.5 1.5 0 0 0 14 4H5.5A1.5 1.5 0 0 0 4 5.5V14a1.5 1.5 0 0 0 1.5 1.5h1"],
    inbox: ["M4 13.5h4l1.5 2.5h5L16 13.5h4", "M6.6 4.5h10.8l2.6 9v5a1.5 1.5 0 0 1-1.5 1.5H5.5A1.5 1.5 0 0 1 4 18.5v-5z"],
  };

  function icon(name, size) {
    const paths = PATHS[name] || [];
    const el = document.createElementNS(NS, "svg");
    el.setAttribute("viewBox", "0 0 24 24");
    el.setAttribute("aria-hidden", "true");
    if (size) {
      el.setAttribute("width", size);
      el.setAttribute("height", size);
    }
    paths.forEach((d) => {
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", d);
      el.appendChild(path);
    });
    return el;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  const FOCUSABLE = 'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

  /* Show a card over the page. Returns { close }. The caller builds the card. */
  function openModal(card, options) {
    const config = options || {};
    const root = document.querySelector("#modal-root");
    if (!root) return { close() {} };

    const lastFocus = document.activeElement;
    root.innerHTML = "";
    root.appendChild(card);
    root.hidden = false;
    document.body.classList.add("is-locked");

    const first = card.querySelector(config.focus || FOCUSABLE);
    if (first) first.focus();

    function close() {
      document.removeEventListener("keydown", onKey);
      root.removeEventListener("mousedown", onBackdrop);
      root.hidden = true;
      root.innerHTML = "";
      document.body.classList.remove("is-locked");
      if (lastFocus && lastFocus.focus) lastFocus.focus();
      if (config.onClose) config.onClose();
    }

    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab") return;
      const stops = Array.from(card.querySelectorAll(FOCUSABLE)).filter((node) => node.offsetParent !== null);
      if (!stops.length) return;
      const at = stops.indexOf(document.activeElement);
      event.preventDefault();
      const next = event.shiftKey ? at - 1 : at + 1;
      stops[(next + stops.length) % stops.length].focus();
    }

    function onBackdrop(event) {
      if (event.target === root) close();
    }

    document.addEventListener("keydown", onKey);
    root.addEventListener("mousedown", onBackdrop);
    return { close };
  }

  /* Confirm dialog. Resolves true when confirmed, false otherwise. */
  function confirmDialog(options) {
    const config = Object.assign(
      { title: "Are you sure?", message: "", confirmLabel: "Confirm", cancelLabel: "Cancel", tone: "brand", iconName: "alert" },
      options || {},
    );
    if (!document.querySelector("#modal-root")) return Promise.resolve(window.confirm(config.title));

    const card = el("div", "modal");
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-labelledby", "modal-title");

    const badge = el("div", config.tone === "danger" ? "modal-icon is-danger" : "modal-icon");
    badge.appendChild(icon(config.iconName));

    const heading = el("h2", null, config.title);
    heading.id = "modal-title";

    const body = el("p");
    if (config.messageHtml) body.innerHTML = config.messageHtml;
    else body.textContent = config.message;

    const actions = el("div", "modal-actions");
    const cancel = el("button", "button secondary", config.cancelLabel);
    cancel.type = "button";
    const confirm = el("button", config.tone === "danger" ? "button danger" : "button", config.confirmLabel);
    confirm.type = "button";
    actions.append(cancel, confirm);
    card.append(badge, heading, body, actions);

    return new Promise((resolve) => {
      let answer = false;
      const modal = openModal(card, {
        focus: ".modal-actions .button:last-child",
        onClose: () => resolve(answer),
      });
      cancel.addEventListener("click", () => modal.close());
      confirm.addEventListener("click", () => {
        answer = true;
        modal.close();
      });
    });
  }

  function toast(message, tone) {
    const stack = document.querySelector("#toast-stack");
    if (!stack) return;
    const node = el("div", tone === "error" ? "toast is-error" : "toast");
    node.setAttribute("role", "status");
    node.append(icon(tone === "error" ? "alert" : "check"), el("span", null, message));
    stack.appendChild(node);
    window.setTimeout(() => {
      node.classList.add("is-out");
      window.setTimeout(() => node.remove(), 220);
    }, 3200);
  }

  /* "2 hours ago" style label, with the full timestamp as a title. */
  function relativeTime(value) {
    if (!value) return { label: "—", title: "" };
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return { label: "—", title: "" };
    const seconds = Math.round((Date.now() - date.getTime()) / 1000);
    const steps = [
      [60, "second", 1],
      [3600, "minute", 60],
      [86400, "hour", 3600],
      [604800, "day", 86400],
      [2629800, "week", 604800],
      [31557600, "month", 2629800],
    ];
    let label = date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    if (seconds < 45) {
      label = "just now";
    } else {
      for (const [limit, unit, divisor] of steps) {
        if (Math.abs(seconds) < limit) {
          const count = Math.round(seconds / divisor);
          label = `${count} ${unit}${count === 1 ? "" : "s"} ago`;
          break;
        }
      }
    }
    return { label, title: date.toLocaleString() };
  }

  function clockTime(date) {
    return (date || new Date()).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  window.UI = { icon, el, openModal, confirmDialog, toast, relativeTime, clockTime };
})();
