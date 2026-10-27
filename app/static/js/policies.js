/* Policy library: a filterable table, icon row actions, and confirmed deletes. */
(function () {
  "use strict";

  const { icon, el, confirmDialog, toast, relativeTime } = window.UI;

  const rows = document.querySelector("#policy-rows");
  const emptyBox = document.querySelector("#policy-empty");
  const count = document.querySelector("#table-count");
  const search = document.querySelector("#policy-search");
  const statusFilter = document.querySelector("#status-filter");
  const errorBox = document.querySelector("#library-error");
  const createButton = document.querySelector("#create-policy");

  const host = document.querySelector("#wizard-host");
  const card = document.querySelector("#wizard-card");
  const progress = document.querySelector("#wizard-progress");
  const subtitle = document.querySelector("#wizard-sub");
  const backButton = document.querySelector("#wizard-back");
  const nextButton = document.querySelector("#wizard-next");
  const leaveRows = document.querySelector("#w-leave-rows");
  const fileInput = document.querySelector("#policy-file");
  const dropzone = document.querySelector("#dropzone");

  /* [metadata key, field, seed] — "template" copies the sample, "" is left blank
     because it names a specific company, document, or date. */
  const META_FIELDS = [
    ["Policy number", "#w-number", ""],
    ["Version", "#w-version", "1.0"],
    ["Effective date", "#w-effective", ""],
    ["Policy owner", "#w-owner", "template"],
    ["Applies to", "#w-applies", "template"],
  ];

  const titleField = () => document.querySelector("#w-title");

  let policies = [];
  let template = null;
  let modal = null;
  let step = "start";
  let working = false;

  /* ---- create wizard ---- */
  createButton.addEventListener("click", openWizard);
  document.querySelector("#wizard-close").addEventListener("click", () => modal && modal.close());
  backButton.addEventListener("click", goBack);
  nextButton.addEventListener("click", goNext);
  document.querySelector("#w-add-leave").addEventListener("click", () => addLeaveRow({}, true));

  document.querySelector("#w-title").addEventListener("input", syncFooter);

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    dropzone.querySelector(".drop-title").textContent = file ? file.name : "Drop a PDF here, or browse";
    syncFooter();
  });

  ["dragenter", "dragover"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-hot");
    });
  });

  ["dragleave", "drop"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-hot");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    if (!event.dataTransfer.files.length) return;
    fileInput.files = event.dataTransfer.files;
    fileInput.dispatchEvent(new Event("change"));
  });

  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.target.tagName === "INPUT" && event.target.type !== "file") {
      event.preventDefault();
      goNext();
    }
  });

  async function openWizard() {
    showError("");
    host.hidden = true;
    step = "start";
    working = false;
    fileInput.value = "";
    dropzone.querySelector(".drop-title").textContent = "Drop a PDF here, or browse";
    modal = window.UI.openModal(card, { onClose: stowWizard, focus: 'input[name="start-kind"]:checked' });
    renderStep();
    if (!template) {
      try {
        template = await (await fetch("/api/authored/template")).json();
      } catch (_error) {
        template = { title: "", metadata: {}, entitlements: [] };
      }
    }
    fillTemplateDefaults();
  }

  function stowWizard() {
    modal = null;
    host.appendChild(card);
  }

  function fillTemplateDefaults() {
    if (!template || leaveRows.childElementCount) return;
    META_FIELDS.forEach(([key, selector, seed]) => {
      const field = document.querySelector(selector);
      if (field.value) return;
      field.value = seed === "template" ? (template.metadata || {})[key] || "" : seed;
    });
    (template.entitlements || []).forEach((row) => addLeaveRow(row, false));
    syncFooter();
  }

  function chosenKind() {
    const picked = card.querySelector('input[name="start-kind"]:checked');
    return picked ? picked.value : "sample";
  }

  function stepsFor(kind) {
    if (kind === "sample") return ["start", "details", "leave"];
    if (kind === "upload") return ["start", "upload"];
    return ["start"];
  }

  function renderStep() {
    const kind = chosenKind();
    const order = stepsFor(kind);
    card.querySelectorAll(".wizard-step").forEach((node) => {
      node.hidden = node.dataset.step !== step;
    });
    progress.hidden = order.length < 2;
    progress.querySelectorAll("li").forEach((node) => {
      const at = order.indexOf(node.dataset.step);
      node.hidden = at === -1;
      node.classList.toggle("is-active", node.dataset.step === step);
      node.classList.toggle("is-done", at !== -1 && at < order.indexOf(step));
    });
    subtitle.textContent = {
      start: "Pick a starting point.",
      details: "These appear in the policy header.",
      upload: "Choose a text-based policy PDF.",
      leave: "Set the leave types and how many days each one gives.",
    }[step];
    syncFooter();
  }

  function syncFooter() {
    const order = stepsFor(chosenKind());
    const at = order.indexOf(step);
    const last = at === order.length - 1;
    backButton.hidden = at <= 0;
    nextButton.textContent = working ? "Working…" : last ? "Create policy" : "Continue";
    const missingTitle = step === "details" && !titleField().value.trim();
    nextButton.disabled = working || missingTitle || (step === "upload" && !fileInput.files.length);
  }

  function goBack() {
    const order = stepsFor(chosenKind());
    const at = order.indexOf(step);
    if (at <= 0) return;
    step = order[at - 1];
    showError("");
    renderStep();
  }

  async function goNext() {
    if (working) return;
    const order = stepsFor(chosenKind());
    const at = order.indexOf(step);
    if (at < order.length - 1) {
      step = order[at + 1];
      showError("");
      renderStep();
      const firstField = card.querySelector(`.wizard-step[data-step="${step}"] input`);
      if (firstField && firstField.type !== "file") firstField.focus();
      return;
    }
    if (step === "upload") await uploadPdf();
    else await createPolicy(chosenKind());
  }

  function addLeaveRow(row, focus) {
    const line = el("div", "leave-row");
    const type = inputCell("Leave type", row.leave_type || "", "Annual Leave");
    const days = inputCell("Entitlement", row.entitlement || "", "20 working days per year");
    const paid = el("select", null);
    ["Yes", "No"].forEach((value) => {
      const option = el("option", null, value);
      option.value = value;
      option.selected = (row.paid || "Yes") === value;
      paid.appendChild(option);
    });
    paid.setAttribute("aria-label", "Paid");
    const remove = el("button", "icon-button is-danger");
    remove.type = "button";
    remove.setAttribute("aria-label", "Remove this leave type");
    remove.appendChild(icon("trash"));
    remove.addEventListener("click", () => line.remove());
    line.append(type, days, paid, remove);
    leaveRows.appendChild(line);
    if (focus) type.focus();
  }

  function inputCell(label, value, placeholder) {
    const input = el("input");
    input.type = "text";
    input.value = value;
    input.placeholder = placeholder;
    input.maxLength = 160;
    input.setAttribute("aria-label", label);
    return input;
  }

  function collectLeaveRows() {
    return Array.from(leaveRows.querySelectorAll(".leave-row"))
      .map((line) => {
        const fields = line.querySelectorAll("input");
        return {
          leave_type: fields[0].value.trim(),
          entitlement: fields[1].value.trim(),
          paid: line.querySelector("select").value,
        };
      })
      .filter((row) => row.leave_type);
  }

  /* The new policy is built but not stored. It joins the library on its first save. */
  async function createPolicy(kind) {
    const payload = { kind: kind === "sample" ? "sample" : "blank" };
    if (kind === "sample") {
      payload.title = titleField().value.trim();
      payload.metadata = {};
      META_FIELDS.forEach(([key, selector]) => {
        payload.metadata[key] = document.querySelector(selector).value.trim();
      });
      payload.entitlements = collectLeaveRows();
      if (!payload.title) {
        step = "details";
        renderStep();
        showError("Give the policy a title first.");
        return;
      }
    }
    setWorking(true);
    try {
      const response = await fetch("/api/authored/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The policy could not be created.");
      if (!stash(data)) await saveNow(data);
      window.location.href = `/policies/${data.id}`;
    } catch (error) {
      showError(error.message);
      setWorking(false);
    }
  }

  function stash(data) {
    try {
      sessionStorage.setItem(`new-policy:${data.id}`, JSON.stringify(data));
      return true;
    } catch (_error) {
      return false;
    }
  }

  /* Storage is blocked, so there is nowhere to hold an unsaved policy: store it now. */
  async function saveNow(data) {
    await fetch(`/api/authored/${data.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }

  async function uploadPdf() {
    const body = new FormData();
    body.append("file", fileInput.files[0]);
    setWorking(true);
    try {
      const response = await fetch("/api/authored/upload", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The PDF could not be added.");
      if (modal) modal.close();
      await loadPolicies();
      toast("The PDF was added to the library.");
    } catch (error) {
      showError(error.message);
    } finally {
      setWorking(false);
    }
  }

  function setWorking(state) {
    working = state;
    syncFooter();
  }

  card.querySelectorAll('input[name="start-kind"]').forEach((radio) => {
    radio.addEventListener("change", renderStep);
  });

  /* ---- table ---- */
  search.addEventListener("input", renderTable);
  statusFilter.addEventListener("change", renderTable);

  loadPolicies();

  async function loadPolicies() {
    try {
      const response = await fetch("/api/authored");
      const data = await response.json();
      policies = data.policies || [];
    } catch (_error) {
      policies = [];
      toast("The policy list could not be loaded.", "error");
    }
    renderStats();
    renderTable();
  }

  function renderStats() {
    const published = policies.filter((item) => item.status === "published").length;
    document.querySelector("#stat-total").textContent = String(policies.length);
    document.querySelector("#stat-published").textContent = String(published);
    document.querySelector("#stat-draft").textContent = String(policies.length - published);
  }

  function visiblePolicies() {
    const term = search.value.trim().toLowerCase();
    const status = statusFilter.value;
    return policies.filter((item) => {
      if (status !== "all" && item.status !== status) return false;
      if (!term) return true;
      return `${item.title} ${item.policy_number || ""} ${item.version || ""}`.toLowerCase().includes(term);
    });
  }

  function renderTable() {
    const shown = visiblePolicies();
    rows.innerHTML = "";
    emptyBox.hidden = shown.length > 0;
    count.textContent = policies.length
      ? `Showing ${shown.length} of ${policies.length} ${policies.length === 1 ? "policy" : "policies"}`
      : "No policies yet";

    if (!shown.length) {
      renderEmpty();
      return;
    }
    shown.forEach((item) => rows.appendChild(policyRow(item)));
  }

  function renderEmpty() {
    emptyBox.innerHTML = "";
    const blank = !policies.length;
    emptyBox.append(
      icon("inbox"),
      el("h3", null, blank ? "No policies yet" : "Nothing matches that filter"),
      el("p", "meta", blank
        ? "Upload a policy PDF, start a blank one, or copy the sample policy."
        : "Clear the search box or choose a different status."),
    );
    if (blank) {
      const action = el("button", "button", "Create policy");
      action.type = "button";
      action.addEventListener("click", openWizard);
      emptyBox.appendChild(action);
    }
  }

  function policyRow(item) {
    const row = document.createElement("tr");
    const published = item.status === "published";

    const titleCell = el("td", "cell-wide");
    titleCell.dataset.label = "Policy";
    const wrap = el("div", "cell-title");
    const badge = el("span", "doc-badge");
    badge.appendChild(icon("doc"));
    const text = el("span");
    const name = el("span", "name", item.title || "Untitled policy");
    name.title = item.title || "Untitled policy";
    text.append(name, el("span", "sub", published ? "Ready for the assistant" : "Draft — not answerable yet"));
    wrap.append(badge, text);
    titleCell.appendChild(wrap);

    const numberCell = el("td", "cell-mono", item.policy_number || "—");
    numberCell.dataset.label = "Policy number";
    if (!item.policy_number) numberCell.classList.add("cell-dim");

    const versionCell = el("td", "cell-mono", item.version || "—");
    versionCell.dataset.label = "Version";
    if (!item.version) versionCell.classList.add("cell-dim");

    const statusCell = el("td");
    statusCell.dataset.label = "Status";
    statusCell.appendChild(el("span", `status-pill ${published ? "is-published" : "is-draft"}`, item.status));

    const stamp = relativeTime(item.updated_at);
    const updatedCell = el("td", "cell-dim", stamp.label);
    updatedCell.dataset.label = "Last updated";
    if (stamp.title) updatedCell.title = stamp.title;

    const actionCell = el("td", "cell-actions");
    actionCell.dataset.label = "Actions";
    const actions = el("div", "icon-actions");
    actions.append(
      iconLink("View", `/policies/${item.id}/view`, "eye"),
      iconLink("Edit", `/policies/${item.id}`, "pencil"),
      iconLink("Download PDF", `/api/authored/${item.id}/pdf`, "download"),
      published
        ? iconButton("Ask the assistant", "chat", () => selectPolicy(item), "")
        : iconButton("Publish", "check", () => publishPolicy(item), "is-ok"),
      iconButton("Delete", "trash", () => removePolicy(item), "is-danger"),
    );
    actionCell.appendChild(actions);

    row.append(titleCell, numberCell, versionCell, statusCell, updatedCell, actionCell);
    return row;
  }

  function iconLink(label, href, iconName) {
    const anchor = el("a", "icon-button");
    anchor.href = href;
    anchor.dataset.tip = label;
    anchor.setAttribute("aria-label", label);
    anchor.appendChild(icon(iconName));
    return anchor;
  }

  function iconButton(label, iconName, handler, tone) {
    const button = el("button", tone ? `icon-button ${tone}` : "icon-button");
    button.type = "button";
    button.dataset.tip = label;
    button.setAttribute("aria-label", label);
    button.appendChild(icon(iconName));
    button.addEventListener("click", handler);
    return button;
  }

  /* ---- actions ---- */

  async function selectPolicy(item) {
    const response = await fetch(`/api/authored/${item.id}/select`, { method: "POST" });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      toast(data.error || "Publish the policy first.", "error");
      return;
    }
    window.location.href = "/";
  }

  async function publishPolicy(item) {
    const ok = await confirmDialog({
      title: "Publish this policy?",
      messageHtml: `<strong>${escapeHtml(item.title || "Untitled policy")}</strong> becomes available to the assistant, and answers will cite its sections.`,
      confirmLabel: "Publish",
      cancelLabel: "Not yet",
      iconName: "check",
    });
    if (!ok) return;
    const response = await fetch(`/api/authored/${item.id}/publish`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      toast(data.error || "The policy could not be published.", "error");
      return;
    }
    await loadPolicies();
    toast("The policy is published.");
  }

  async function removePolicy(item) {
    const ok = await confirmDialog({
      title: "Delete this policy?",
      messageHtml: `<strong>${escapeHtml(item.title || "Untitled policy")}</strong> will be removed from the library. This cannot be undone.`,
      confirmLabel: "Delete policy",
      cancelLabel: "Keep it",
      tone: "danger",
      iconName: "trash",
    });
    if (!ok) return;
    const response = await fetch(`/api/authored/${item.id}`, { method: "DELETE" });
    if (!response.ok) {
      toast("The policy could not be deleted.", "error");
      return;
    }
    await loadPolicies();
    toast("The policy was deleted.");
  }

  /* Wizard-only: the box lives inside the card. Table errors use toasts. */
  function showError(message) {
    errorBox.hidden = !message;
    errorBox.textContent = message;
  }

  function escapeHtml(value) {
    const node = document.createElement("span");
    node.textContent = value;
    return node.innerHTML;
  }
})();
