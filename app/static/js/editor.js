/* Policy editor: an outline on the left, one section at a time on the right. */
(function () {
  "use strict";

  const { icon, el, confirmDialog, toast } = window.UI;

  const mount = document.querySelector("#editor-app");
  const policyId = mount.dataset.id;
  const outline = document.querySelector("#outline");
  const pane = document.querySelector("#editor-pane");
  const errorBox = document.querySelector("#editor-error");
  const titleBox = document.querySelector("#editor-title");
  const statusPill = document.querySelector("#editor-status");
  const dirtyFlag = document.querySelector("#editor-dirty");
  const actions = document.querySelector("#editor-actions");

  /* Responses come back with sorted keys, so the header fields get a fixed order. */
  const META_ORDER = ["Policy number", "Version", "Effective date", "Policy owner", "Applies to"];

  const KINDS = [
    ["text", "Text and clauses"],
    ["entitlements", "Entitlements table"],
    ["roles", "Roles table"],
  ];

  const stashKey = `new-policy:${policyId}`;

  let draft = null;
  let active = "details";
  let dirty = false;
  let saved = true;
  const openSubs = new Set();

  window.addEventListener("beforeunload", (event) => {
    if (!dirty) return;
    /* Hold an unsaved policy, so a reload does not throw the wizard's work away. */
    if (!saved) stash();
    event.preventDefault();
    event.returnValue = "";
  });

  outline.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const tabs = Array.from(outline.querySelectorAll('[role="tab"]'));
    const at = tabs.indexOf(document.activeElement);
    if (at === -1) return;
    event.preventDefault();
    const next = tabs[(at + (event.key === "ArrowDown" ? 1 : -1) + tabs.length) % tabs.length];
    next.focus();
    next.click();
  });

  load();

  async function load() {
    const response = await fetch(`/api/authored/${policyId}`);
    if (response.ok) {
      draft = await response.json();
      saved = true;
    } else {
      /* A policy built by the wizard is not in the library until it is saved. */
      draft = unstash();
      if (!draft) {
        showError("That policy was not found.");
        return;
      }
      saved = false;
      dirty = true;
    }
    renderAll();
  }

  function stash() {
    try {
      sessionStorage.setItem(stashKey, JSON.stringify(draft));
    } catch (_error) {
      /* Nothing to do: the draft stays in memory for this page view. */
    }
  }

  function unstash() {
    try {
      const held = sessionStorage.getItem(stashKey);
      return held ? JSON.parse(held) : null;
    } catch (_error) {
      return null;
    }
  }

  function forget() {
    try {
      sessionStorage.removeItem(stashKey);
    } catch (_error) {
      /* Already gone, or storage is blocked. */
    }
  }

  function renderAll() {
    renderBar();
    renderOutline();
    renderPane();
  }

  /* ---- top bar ---- */
  function renderBar() {
    const published = draft.status === "published";
    titleBox.textContent = draft.title || "Untitled policy";
    statusPill.textContent = draft.status;
    statusPill.className = `status-pill ${published ? "is-published" : "is-draft"}`;
    dirtyFlag.hidden = !dirty;
    dirtyFlag.textContent = saved ? "Unsaved changes" : "Not saved yet";

    actions.innerHTML = "";
    let preview;
    if (saved) {
      preview = el("a", "small-button", "Preview PDF");
      preview.href = `/policies/${policyId}/view`;
    } else {
      preview = el("button", "small-button", "Preview PDF");
      preview.type = "button";
      preview.disabled = true;
      preview.dataset.tip = "Save the draft first";
    }
    const save = button("Save draft", "button secondary", saveDraft);
    const publish = button(published ? "Republish" : "Publish", "button", publishDraft);
    actions.append(preview, save, publish);
    if (published) actions.insertBefore(button("Back to draft", "small-button", unpublishDraft), save);
  }

  /* ---- outline ---- */
  function renderOutline() {
    outline.innerHTML = "";
    outline.appendChild(tab("details", null, "Policy details", "Title, number, version"));

    const group = el("p", "outline-label", "Sections");
    outline.appendChild(group);

    draft.sections.forEach((section, index) => {
      const children = section.subsections.length;
      const note = children ? `${children} subsection${children === 1 ? "" : "s"}` : "No subsections";
      outline.appendChild(tab(index, String(index + 1), section.heading || "Untitled section", note));
    });

    const add = el("button", "outline-add");
    add.type = "button";
    add.append(icon("plus"), el("span", null, "Add section"));
    add.addEventListener("click", () => {
      draft.sections.push({ heading: "New section", body: "", subsections: [] });
      active = draft.sections.length - 1;
      markDirty();
      renderAll();
    });
    outline.appendChild(add);
  }

  function tab(key, number, label, note) {
    const node = el("button", "outline-item");
    node.type = "button";
    node.setAttribute("role", "tab");
    const on = String(active) === String(key);
    node.setAttribute("aria-selected", on ? "true" : "false");
    node.tabIndex = on ? 0 : -1;
    if (on) node.classList.add("is-active");
    const chip = el("span", "outline-no");
    if (number) chip.textContent = number;
    else chip.appendChild(icon("doc"));
    node.appendChild(chip);
    const text = el("span", "outline-text");
    text.append(el("strong", null, label), el("span", null, note));
    node.appendChild(text);
    node.addEventListener("click", () => {
      active = key;
      renderOutline();
      renderPane();
      pane.focus({ preventScroll: true });
    });
    return node;
  }

  /* ---- panes ---- */
  function renderPane() {
    pane.innerHTML = "";
    pane.append(active === "details" ? detailsPane() : sectionPane(draft.sections[active], active));
    pane.scrollTop = 0;
  }

  function detailsPane() {
    const wrap = el("div");
    wrap.append(paneHead("Policy details", "These appear in the header of the policy PDF."));
    wrap.append(field("Policy title", draft.title, (value) => {
      draft.title = value;
      titleBox.textContent = value || "Untitled policy";
    }));
    wrap.append(area("Opening note", draft.disclaimer, (value) => { draft.disclaimer = value; }, 3));
    const grid = el("div", "grid-2");
    const keys = Object.keys(draft.metadata);
    const ordered = META_ORDER.filter((key) => keys.includes(key)).concat(keys.filter((key) => !META_ORDER.includes(key)));
    ordered.forEach((key) => {
      grid.append(field(key, draft.metadata[key], (value) => { draft.metadata[key] = value; }));
    });
    wrap.appendChild(grid);
    wrap.appendChild(el("p", "meta",
      "Sections are numbered 1, 2, 3. Subsections become 2.1, 2.2. If the first subsection is an entitlements table, it is numbered 4.0, like the sample. Clauses are (a), (b), (c)."));
    return wrap;
  }

  function sectionPane(section, index) {
    const wrap = el("div");
    const head = paneHead(`Section ${index + 1}`, "Give the section a heading, then add text or subsections.");
    const remove = el("button", "small-button danger-text", "Remove section");
    remove.type = "button";
    remove.addEventListener("click", () => removeSection(section, index));
    head.appendChild(remove);
    wrap.appendChild(head);

    wrap.append(field("Heading", section.heading, (value) => {
      section.heading = value;
      refreshOutlineLabels();
    }));
    wrap.append(area("Section text", section.body, (value) => { section.body = value; }, 4));

    const list = el("div", "sub-list");
    section.subsections.forEach((child, childIndex) => {
      list.appendChild(subsectionCard(section, child, index, childIndex));
    });
    wrap.appendChild(list);

    const add = el("button", "button secondary", "Add subsection");
    add.type = "button";
    add.addEventListener("click", () => {
      section.subsections.push({ heading: "", kind: "text", body: "", clauses: [], rows: [] });
      openSubs.add(subKey(index, section.subsections.length - 1));
      markDirty();
      renderOutline();
      renderPane();
    });
    wrap.appendChild(add);
    return wrap;
  }

  function subsectionCard(section, child, sectionIndex, childIndex) {
    const key = subKey(sectionIndex, childIndex);
    const box = el("details", "sub-card");
    box.open = openSubs.has(key);
    box.addEventListener("toggle", () => {
      if (box.open) openSubs.add(key);
      else openSubs.delete(key);
    });

    const summary = el("summary");
    summary.append(el("span", "sub-no", childNumber(section, sectionIndex, childIndex)));
    summary.append(el("span", "sub-name", child.heading || sectionLabel(child)));
    summary.append(el("span", `sub-kind is-${child.kind}`, kindLabel(child.kind)));
    box.appendChild(summary);

    const body = el("div", "sub-body");
    body.append(field("Heading, if this subsection has one", child.heading, (value) => {
      child.heading = value;
      summary.querySelector(".sub-name").textContent = value || sectionLabel(child);
    }));

    const kind = el("label", "field");
    kind.append(el("span", null, "Subsection type"));
    const select = el("select");
    KINDS.forEach(([value, name]) => {
      const option = el("option", null, name);
      option.value = value;
      option.selected = child.kind === value;
      select.appendChild(option);
    });
    select.addEventListener("change", () => {
      child.kind = select.value;
      openSubs.add(key);
      markDirty();
      renderPane();
    });
    kind.appendChild(select);
    body.appendChild(kind);

    if (child.kind === "text") body.appendChild(textEditor(child, key));
    if (child.kind === "entitlements") body.appendChild(entitlementEditor(child, key));
    if (child.kind === "roles") body.appendChild(roleEditor(child, key));

    const remove = el("button", "small-button danger-text", "Remove subsection");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      const ok = await confirmDialog({
        title: "Remove this subsection?",
        messageHtml: `<strong>Subsection ${childNumber(section, sectionIndex, childIndex)}</strong> will be removed from the draft.`,
        confirmLabel: "Remove subsection",
        cancelLabel: "Keep it",
        tone: "danger",
        iconName: "trash",
      });
      if (!ok) return;
      section.subsections.splice(childIndex, 1);
      openSubs.clear();
      markDirty();
      renderOutline();
      renderPane();
    });
    body.appendChild(remove);

    box.appendChild(body);
    return box;
  }

  function textEditor(child, key) {
    const wrap = el("div");
    wrap.append(area("Subsection text", child.body, (value) => { child.body = value; }, 3));
    child.clauses.forEach((clause, clauseIndex) => {
      const row = el("div", "clause-row");
      row.append(area(`Clause (${letter(clauseIndex)})`, clause, (value) => { child.clauses[clauseIndex] = value; }, 2));
      const drop = el("button", "icon-button is-danger");
      drop.type = "button";
      drop.setAttribute("aria-label", `Remove clause (${letter(clauseIndex)})`);
      drop.appendChild(icon("trash"));
      drop.addEventListener("click", () => {
        child.clauses.splice(clauseIndex, 1);
        openSubs.add(key);
        markDirty();
        renderPane();
      });
      row.appendChild(drop);
      wrap.appendChild(row);
    });
    wrap.append(adder("Add clause", () => {
      child.clauses.push("");
      openSubs.add(key);
      renderPane();
    }));
    return wrap;
  }

  function entitlementEditor(child, key) {
    const wrap = el("div", "table-editor");
    const header = el("div", "row-4 table-editor-head");
    ["Leave type", "Entitlement", "Paid", "Section"].forEach((label) => header.append(el("span", null, label)));
    header.append(el("span"));
    wrap.appendChild(header);

    child.rows.forEach((row, index) => {
      const line = el("div", "row-4");
      line.append(
        cell("Leave type", row.leave_type, (value) => { row.leave_type = value; }, "Annual Leave"),
        cell("Entitlement", row.entitlement, (value) => { row.entitlement = value; }, "20 working days per year"),
        paidCell(row),
        cell("Section", row.section, (value) => { row.section = value; }, "4.1"),
        dropButton(`Remove ${row.leave_type || "this leave type"}`, () => {
          child.rows.splice(index, 1);
          openSubs.add(key);
          markDirty();
          renderPane();
        }),
      );
      wrap.appendChild(line);
    });

    wrap.append(adder("Add leave type", () => {
      child.rows.push({ leave_type: "", entitlement: "", paid: "Yes", section: "" });
      openSubs.add(key);
      renderPane();
    }));
    return wrap;
  }

  function roleEditor(child, key) {
    const wrap = el("div", "table-editor");
    child.rows.forEach((row, index) => {
      const line = el("div", "role-row");
      line.append(
        cell("Role", row.role, (value) => { row.role = value; }, "Line manager"),
        cell("Responsibility", row.responsibility, (value) => { row.responsibility = value; }, "Approves leave within three working days"),
        dropButton(`Remove ${row.role || "this role"}`, () => {
          child.rows.splice(index, 1);
          openSubs.add(key);
          markDirty();
          renderPane();
        }),
      );
      wrap.appendChild(line);
    });
    wrap.append(adder("Add role", () => {
      child.rows.push({ role: "", responsibility: "" });
      openSubs.add(key);
      renderPane();
    }));
    return wrap;
  }

  /* ---- saving ---- */
  async function saveDraft() {
    showError("");
    const response = await fetch(`/api/authored/${policyId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "The draft could not be saved.");
      return false;
    }
    const first = !saved;
    draft = data;
    dirty = false;
    saved = true;
    forget();
    if (active !== "details" && active >= draft.sections.length) active = "details";
    renderAll();
    toast(first ? "The policy was saved to the library." : "The draft was saved.");
    return true;
  }

  async function publishDraft() {
    const ok = await confirmDialog({
      title: "Publish this policy?",
      messageHtml: `<strong>${escapeHtml(draft.title || "Untitled policy")}</strong> becomes available to the assistant, and answers will cite its sections.`,
      confirmLabel: "Publish",
      cancelLabel: "Not yet",
      iconName: "check",
    });
    if (!ok) return;
    if (!(await saveDraft())) return;
    const response = await fetch(`/api/authored/${policyId}/publish`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "The policy could not be published.");
      return;
    }
    dirty = false;
    saved = true;
    forget();
    window.location.href = "/";
  }

  async function unpublishDraft() {
    const response = await fetch(`/api/authored/${policyId}/unpublish`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "The policy could not return to draft.");
      return;
    }
    draft = data;
    dirty = false;
    renderAll();
    toast("The policy is back to draft.");
  }

  async function removeSection(section, index) {
    const ok = await confirmDialog({
      title: "Remove this section?",
      messageHtml: `<strong>Section ${index + 1} — ${escapeHtml(section.heading || "Untitled section")}</strong> and everything inside it will be removed from the draft.`,
      confirmLabel: "Remove section",
      cancelLabel: "Keep it",
      tone: "danger",
      iconName: "trash",
    });
    if (!ok) return;
    draft.sections.splice(index, 1);
    if (!draft.sections.length) draft.sections.push({ heading: "Purpose", body: "", subsections: [] });
    openSubs.clear();
    active = draft.sections.length ? Math.min(index, draft.sections.length - 1) : "details";
    markDirty();
    renderAll();
  }

  /* ---- small builders ---- */
  function paneHead(title, note) {
    const head = el("div", "pane-head");
    const text = el("div");
    text.append(el("h2", null, title), el("p", "meta", note));
    head.appendChild(text);
    return head;
  }

  function field(label, value, setter) {
    const wrap = el("label", "field");
    const input = el("input");
    input.type = "text";
    input.value = value || "";
    input.addEventListener("input", () => {
      setter(input.value);
      markDirty();
    });
    wrap.append(el("span", null, label), input);
    return wrap;
  }

  function area(label, value, setter, rows) {
    const wrap = el("label", "field");
    const input = el("textarea");
    input.rows = rows || 3;
    input.value = value || "";
    input.addEventListener("input", () => {
      setter(input.value);
      markDirty();
    });
    wrap.append(el("span", null, label), input);
    return wrap;
  }

  function cell(label, value, setter, placeholder) {
    const input = el("input");
    input.type = "text";
    input.value = value || "";
    input.placeholder = placeholder || "";
    input.setAttribute("aria-label", label);
    input.addEventListener("input", () => {
      setter(input.value);
      markDirty();
    });
    return input;
  }

  function paidCell(row) {
    const select = el("select");
    ["Yes", "No"].forEach((value) => {
      const option = el("option", null, value);
      option.value = value;
      option.selected = (row.paid || "Yes") === value;
      select.appendChild(option);
    });
    select.setAttribute("aria-label", "Paid");
    select.addEventListener("change", () => {
      row.paid = select.value;
      markDirty();
    });
    return select;
  }

  function dropButton(label, handler) {
    const node = el("button", "icon-button is-danger");
    node.type = "button";
    node.setAttribute("aria-label", label);
    node.appendChild(icon("trash"));
    node.addEventListener("click", handler);
    return node;
  }

  function adder(label, handler) {
    const node = el("button", "small-button");
    node.type = "button";
    node.append(icon("plus"), el("span", null, label));
    node.addEventListener("click", () => {
      markDirty();
      handler();
    });
    return node;
  }

  function button(label, className, handler) {
    const node = el("button", className, label);
    node.type = "button";
    node.addEventListener("click", handler);
    return node;
  }

  /* ---- helpers ---- */
  function markDirty() {
    dirty = true;
    dirtyFlag.hidden = false;
  }

  function refreshOutlineLabels() {
    markDirty();
    const tabs = outline.querySelectorAll('[role="tab"]');
    draft.sections.forEach((section, index) => {
      const node = tabs[index + 1];
      if (node) node.querySelector("strong").textContent = section.heading || "Untitled section";
    });
  }

  function childNumber(section, sectionIndex, childIndex) {
    const start = section.subsections[0] && section.subsections[0].kind === "entitlements" ? 0 : 1;
    return `${sectionIndex + 1}.${start + childIndex}`;
  }

  function subKey(sectionIndex, childIndex) {
    return `${sectionIndex}:${childIndex}`;
  }

  function sectionLabel(child) {
    return child.kind === "entitlements" ? "Entitlements table" : child.kind === "roles" ? "Roles table" : "Untitled subsection";
  }

  function kindLabel(kind) {
    const found = KINDS.find(([value]) => value === kind);
    return found ? found[1] : "Text";
  }

  function letter(index) {
    return String.fromCharCode(97 + index);
  }

  function escapeHtml(value) {
    const node = document.createElement("span");
    node.textContent = value;
    return node.innerHTML;
  }

  function showError(message) {
    errorBox.hidden = !message;
    errorBox.textContent = message;
  }
})();
