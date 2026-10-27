/* Assistant chat: policy picker, thinking states, typed replies, cited sources. */
(function () {
  "use strict";

  const { icon, el, toast, clockTime } = window.UI;

  const transcript = document.querySelector("#transcript");
  const askForm = document.querySelector("#ask-form");
  const questionInput = document.querySelector("#question");
  const askButton = document.querySelector("#ask-button");
  const choices = document.querySelector("#policy-choices");
  const chooserError = document.querySelector("#chooser-error");
  const botState = document.querySelector("#bot-state");
  const resetButton = document.querySelector("#reset-chat");
  const chipRow = document.querySelector("#chip-row");
  const charCount = document.querySelector("#char-count");
  const scrollEnd = document.querySelector("#scroll-end");
  const intro = document.querySelector("#chat-intro");
  const introTemplate = intro.cloneNode(true);

  /* Tag, the question it asks, and which of the three behaviours it shows.
     The tag is short enough to scan; the full question appears on hover. */
  const TAGS = [
    ["Casual leave", "How many casual leave days do I get in a year?", "answer"],
    ["Annual leave", "How many annual leave days do I get?", "answer"],
    ["Sick leave", "When do I need a medical certificate for sick leave?", "answer"],
    ["Maternity", "How much notice must I give HR before maternity leave?", "answer"],
    ["Apply", "How do I apply for leave?", "answer"],
    ["Approval", "How long does my manager have to approve my leave request?", "answer"],
    ["Probation", "Can I take annual leave during probation?", "answer"],
    ["Notice period", "Can I take annual leave during my notice period?", "answer"],
    ["Holidays", "Do public holidays during my annual leave count as leave days?", "answer"],
    ["Records", "Who can see my leave records?", "answer"],
    ["Not covered", "Can I take study leave?", "unknown"],
    ["Someone else", "How many leave days has Rahim taken?", "privacy"],
  ];

  const THINKING = [
    "Reading the policy…",
    "Looking for the matching section…",
    "Checking the figures against the document…",
    "Writing the answer…",
  ];

  const KIND_LABEL = {
    answer: "From the policy",
    unknown: "Not in the policy",
    privacy: "Confidential",
    error: "Something went wrong",
  };

  let chatEnabled = false;
  let busy = false;
  let selectedId = "";
  let selectedTitle = "";

  /* ---- events ---- */
  askForm.addEventListener("submit", (event) => {
    event.preventDefault();
    ask(questionInput.value);
  });

  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askForm.requestSubmit();
    }
  });

  questionInput.addEventListener("input", () => {
    grow();
    charCount.textContent = `${questionInput.value.length} / 1000`;
    askButton.disabled = busy || !chatEnabled || !questionInput.value.trim();
  });

  resetButton.addEventListener("click", () => {
    if (busy) return;
    startChat(selectedTitle, true);
  });

  transcript.addEventListener("scroll", () => {
    const gap = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight;
    scrollEnd.hidden = gap < 90;
  });

  scrollEnd.addEventListener("click", () => scrollToEnd(true));

  bindSuggestions();
  loadDesk();

  /* ---- loading ---- */
  async function loadDesk() {
    const [current, listed] = await Promise.all([
      fetch("/api/policy").catch(() => null),
      fetch("/api/authored").catch(() => null),
    ]);
    const policies = listed && listed.ok ? ((await listed.json()).policies || []) : [];
    const published = policies.filter((item) => item.status === "published");

    let currentId = "";
    if (current && current.ok) {
      const data = await current.json();
      currentId = data.policy_id || "";
      selectedId = currentId;
      selectedTitle = data.title || "";
      chatEnabled = Boolean(data.chat_enabled);
      startChat(selectedTitle, true);
    } else {
      setAskingEnabled(false);
      botState.textContent = published.length
        ? "Choose a published policy to begin"
        : "No published policy yet";
    }
    renderChoices(published, currentId);
  }

  function renderChoices(policies, currentId) {
    choices.innerHTML = "";
    if (!policies.length) {
      const note = el("p", "meta");
      note.append("No published policy yet. ");
      const link = el("a", null, "Create or upload one under Policies");
      link.href = "/policies";
      note.append(link, ".");
      choices.appendChild(note);
      return;
    }
    policies.forEach((item) => {
      const button = el("button", "choice");
      button.type = "button";
      button.dataset.id = item.id;
      button.setAttribute("aria-pressed", item.id === currentId ? "true" : "false");
      if (item.id === currentId) button.classList.add("is-selected");
      const label = [item.policy_number, item.version].filter(Boolean).join(" · ");
      button.append(el("span", null, item.title || "Untitled policy"));
      if (label) button.append(el("span", "sub", ` ${label}`));
      button.addEventListener("click", () => selectPublished(item));
      choices.appendChild(button);
    });
  }

  async function selectPublished(item) {
    if (busy || item.id === selectedId) return;
    setBusy(true);
    showError("");
    botState.textContent = "Opening the policy…";
    try {
      const response = await fetch(`/api/authored/${item.id}/select`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "That policy could not be opened.");
      selectedId = data.policy_id || item.id;
      selectedTitle = data.title || item.title || "";
      chatEnabled = Boolean(data.chat_enabled);
      document.querySelectorAll(".choice").forEach((button) => {
        const on = button.dataset.id === item.id;
        button.classList.toggle("is-selected", on);
        button.setAttribute("aria-pressed", on ? "true" : "false");
      });
      startChat(selectedTitle, true);
      toast(`${selectedTitle || "The policy"} is loaded.`);
    } catch (error) {
      showError(error.message);
      botState.textContent = "Choose a published policy to begin";
    } finally {
      setBusy(false);
    }
  }

  /* ---- chat surface ---- */
  function startChat(title, announce) {
    transcript.innerHTML = "";
    transcript.appendChild(introTemplate.cloneNode(true));
    bindSuggestions();
    renderChips();
    setAskingEnabled(chatEnabled);
    resetButton.disabled = !chatEnabled;
    botState.textContent = chatEnabled
      ? `Reading ${title || "the selected policy"}`
      : "Choose a published policy to begin";
    if (chatEnabled && announce) {
      addBotMessage(
        "answer",
        `${title || "This policy"} is loaded. Ask me anything it covers — I will quote the section I used.`,
        [],
        { badge: false, typed: true },
      );
    }
    scrollToEnd(false);
  }

  function bindSuggestions() {
    transcript.querySelectorAll("[data-question]").forEach((button) => {
      button.disabled = !chatEnabled;
      button.addEventListener("click", () => ask(button.dataset.question));
    });
  }

  function renderChips() {
    chipRow.innerHTML = "";
    chipRow.hidden = !chatEnabled;
    if (!chatEnabled) return;
    chipRow.appendChild(el("span", "chip-label", "Try"));
    TAGS.forEach(([label, question, kind]) => {
      const chip = el("button", `quick-chip is-${kind}`, label);
      chip.type = "button";
      chip.dataset.tip = question;
      chip.setAttribute("aria-label", question);
      chip.addEventListener("click", () => ask(question));
      chipRow.appendChild(chip);
    });
  }

  async function ask(raw) {
    const question = (raw || "").trim();
    if (!question || busy || !chatEnabled) return;

    const placeholder = transcript.querySelector("#chat-intro");
    if (placeholder) placeholder.remove();

    questionInput.value = "";
    grow();
    charCount.textContent = "0 / 1000";
    addUserMessage(question);
    setBusy(true);

    const thinking = addThinking();
    const started = Date.now();
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The question could not be answered.");
      await hold(started, 650);
      thinking.stop();
      const parts = splitSource(data.text || "");
      addBotMessage(data.kind || "answer", parts.body, data.citations || [], { typed: true, note: parts.source });
    } catch (error) {
      await hold(started, 350);
      thinking.stop();
      addBotMessage("error", error.message, [], { typed: false });
    } finally {
      setBusy(false);
      questionInput.focus();
    }
  }

  /* ---- messages ---- */
  function addUserMessage(text) {
    const row = el("div", "msg is-user");
    const avatar = el("span", "avatar");
    avatar.appendChild(icon("user"));
    const stack = el("div", "stack");
    const foot = el("div", "msg-foot");
    foot.appendChild(el("span", "msg-time", clockTime()));
    stack.append(el("div", "bubble", text), foot);
    row.append(avatar, stack);
    transcript.appendChild(row);
    scrollToEnd(false);
    return row;
  }

  function addBotMessage(kind, text, citations, options) {
    const config = options || {};
    const row = el("div", `msg is-${kind}`);
    const avatar = el("span", "avatar");
    avatar.appendChild(icon("bot"));
    const stack = el("div", "stack");
    const bubble = el("div", "bubble");

    if (config.badge !== false && KIND_LABEL[kind]) {
      bubble.appendChild(el("span", `msg-kind is-${kind}`, KIND_LABEL[kind]));
    }
    const body = el("div");
    bubble.appendChild(body);
    const foot = el("div", "msg-foot");
    foot.appendChild(el("span", "msg-time", clockTime()));
    stack.append(bubble, foot);
    row.append(avatar, stack);
    transcript.appendChild(row);

    const finish = () => {
      const sources = sourceBlock(citations, config.note);
      if (sources) bubble.appendChild(sources);
      if (kind !== "error") foot.appendChild(copyButton(text, config.note));
      if (nearBottom()) scrollToEnd(false);
    };

    if (config.typed) {
      body.setAttribute("aria-busy", "true");
      typeInto(body, text, () => {
        body.removeAttribute("aria-busy");
        finish();
      });
    }
    else {
      body.textContent = text;
      finish();
    }
    scrollToEnd(false);
    return row;
  }

  /* A reply is something an employee may want to forward to HR. */
  function copyButton(text, note) {
    const copy = el("button", "ghost-button");
    copy.type = "button";
    copy.append(icon("copy"), el("span", null, "Copy"));
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(note ? `${text}\n\n${note}` : text);
        copy.querySelector("span").textContent = "Copied";
        window.setTimeout(() => {
          copy.querySelector("span").textContent = "Copy";
        }, 1600);
      } catch (_error) {
        toast("Copying is blocked in this browser.", "error");
      }
    });
    return copy;
  }

  function sourceBlock(citations, note) {
    const list = citations && citations.length ? citations : [];
    if (!list.length && !note) return null;
    const wrap = el("div", "sources");
    wrap.appendChild(el("span", "label", "Source"));
    if (list.length) {
      list.forEach((item) => {
        const chip = el("span", "source-chip");
        chip.append(el("b", null, `§ ${item.id}`), document.createTextNode(item.heading || ""));
        wrap.appendChild(chip);
      });
    } else {
      wrap.appendChild(el("span", "source-chip", note.replace(/^Source:\s*/i, "").replace(/\.$/, "")));
    }
    return wrap;
  }

  function addThinking() {
    const row = el("div", "msg is-answer");
    const avatar = el("span", "avatar");
    avatar.appendChild(icon("bot"));
    const stack = el("div", "stack");
    const bubble = el("div", "bubble is-thinking");
    const typing = el("div", "typing");
    const dots = el("span", "dots");
    dots.append(el("i"), el("i"), el("i"));
    const label = el("span", "typing-label", THINKING[0]);
    typing.append(dots, label);
    bubble.appendChild(typing);
    stack.appendChild(bubble);
    row.append(avatar, stack);
    transcript.appendChild(row);
    scrollToEnd(false);

    let step = 0;
    const timer = window.setInterval(() => {
      step = (step + 1) % THINKING.length;
      label.textContent = THINKING[step];
    }, 1100);

    return {
      stop() {
        window.clearInterval(timer);
        row.remove();
      },
    };
  }

  /* Reveal the reply a few characters at a time, so it reads as a live answer. */
  function typeInto(node, text, done) {
    if (!text) {
      if (done) done();
      return;
    }
    const slice = document.createTextNode("");
    const caret = el("span", "caret");
    node.append(slice, caret);
    const chunk = Math.max(2, Math.ceil(text.length / 110));
    let at = 0;
    let ticks = 0;
    const timer = window.setInterval(() => {
      at = Math.min(text.length, at + chunk);
      slice.data = text.slice(0, at);
      if (ticks++ % 2 === 0 && nearBottom()) scrollToEnd(false);
      if (at >= text.length) {
        window.clearInterval(timer);
        caret.remove();
        if (done) done();
      }
    }, 16);
  }

  function splitSource(text) {
    const match = text.match(/\n*\s*(Source:[\s\S]*)$/);
    if (!match) return { body: text.trim(), source: "" };
    return { body: text.slice(0, match.index).trim(), source: match[1].trim() };
  }

  function hold(started, minimum) {
    const left = minimum - (Date.now() - started);
    return left > 0 ? new Promise((resolve) => window.setTimeout(resolve, left)) : Promise.resolve();
  }

  /* ---- state ---- */
  function setAskingEnabled(enabled) {
    questionInput.disabled = !enabled;
    questionInput.placeholder = enabled
      ? "Ask about leave in the selected policy…"
      : "Select a policy first…";
    askButton.disabled = !enabled || !questionInput.value.trim();
    transcript.querySelectorAll("[data-question]").forEach((button) => {
      button.disabled = !enabled;
    });
    chipRow.querySelectorAll("button").forEach((button) => {
      button.disabled = !enabled;
    });
  }

  function setBusy(state) {
    busy = state;
    askButton.disabled = state || !chatEnabled || !questionInput.value.trim();
    questionInput.disabled = state || !chatEnabled;
    resetButton.disabled = state || !chatEnabled;
    transcript.querySelectorAll("[data-question]").forEach((button) => {
      button.disabled = state || !chatEnabled;
    });
    chipRow.querySelectorAll("button").forEach((button) => {
      button.disabled = state || !chatEnabled;
    });
    if (state) botState.textContent = "Checking the policy…";
    else if (chatEnabled) botState.textContent = `Reading ${selectedTitle || "the selected policy"}`;
  }

  function grow() {
    questionInput.style.height = "auto";
    questionInput.style.height = `${Math.min(questionInput.scrollHeight, 160)}px`;
  }

  function nearBottom() {
    return transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 180;
  }

  function scrollToEnd(smooth) {
    transcript.scrollTo({ top: transcript.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    scrollEnd.hidden = true;
  }

  function showError(message) {
    chooserError.hidden = !message;
    chooserError.textContent = message;
  }
})();
