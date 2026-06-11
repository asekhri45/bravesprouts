document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("askForm");
  const input = document.getElementById("askInput");
  const suggestionButtons = document.querySelectorAll(".suggestion-pill");
  const askPage = document.querySelector(".ask-page");
  const hero = document.querySelector(".ask-hero");
  const plusButton = document.querySelector(".ask-plus-btn");

function autoResizeInput() {
  input.style.height = "auto";

  const nextHeight = Math.min(input.scrollHeight, 130);
  input.style.height = `${Math.max(nextHeight, 28)}px`;

  form.style.minHeight = `${Math.max(70, nextHeight + 28)}px`;
}

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", autoResizeInput);
autoResizeInput();

  let currentConversationId = null;
  let isSending = false;
  let sidebarOpen = false;

  const chatArea = document.createElement("div");
  chatArea.className = "ask-chat-area";
  chatArea.setAttribute("aria-live", "polite");
  hero.appendChild(chatArea);

  const sidebar = document.createElement("aside");
  sidebar.className = "ask-history-sidebar";

  sidebar.innerHTML = `
    <button type="button" class="ask-history-toggle" aria-label="Toggle chat history">
      ☰
    </button>

    <div class="ask-history-panel">
      <div class="ask-history-header">
        <div>
          <h3>Past chats</h3>
          <p>Continue a previous conversation</p>
        </div>

        <button type="button" class="ask-history-close" aria-label="Close chat history">
          ×
        </button>
      </div>

      <button type="button" class="ask-new-chat-btn">
        + New chat
      </button>

      <div class="ask-history-list" id="askHistoryList">
        <p class="ask-history-empty">No chats yet.</p>
      </div>
    </div>
  `;

  askPage.appendChild(sidebar);

  const historyToggle = sidebar.querySelector(".ask-history-toggle");
  const historyClose = sidebar.querySelector(".ask-history-close");
  const newChatButton = sidebar.querySelector(".ask-new-chat-btn");
  const historyList = sidebar.querySelector("#askHistoryList");

  function openSidebar() {
    sidebarOpen = true;
    sidebar.classList.add("open");
    loadConversations();
  }

  function closeSidebar() {
    sidebarOpen = false;
    sidebar.classList.remove("open");
  }

  function toggleSidebar() {
    if (sidebarOpen) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  function renderBotCard(ai) {
    const normalized = normalizeAssistantMessage(ai);

    const theme = normalized.theme || "purple";
    const confidence = normalized.confidence || "unclear";

    const card = document.createElement("div");
    card.className = `ask-response-card ask-theme-${theme} ask-layout-${normalized.layout_type || "quick"}`;

    const heroBlock = document.createElement("div");
    heroBlock.className = "ask-card-hero";

    const heroText = document.createElement("div");
    heroText.className = "ask-card-hero-text";

    const eyebrow = document.createElement("div");
    eyebrow.className = "ask-card-eyebrow";
    eyebrow.textContent = normalized.hero?.eyebrow || "BraveSprouts Guide";

    const title = document.createElement("h3");
    title.textContent =
      normalized.hero?.title ||
      normalized.title ||
      "Response";

    const summary = document.createElement("p");
    summary.textContent =
      normalized.hero?.summary ||
      "";

    heroText.appendChild(eyebrow);
    heroText.appendChild(title);

    if (summary.textContent.trim()) {
      heroText.appendChild(summary);
    }

    const badge = document.createElement("div");
    badge.className = `ask-confidence-badge confidence-${confidence}`;
    badge.textContent = confidenceLabel(confidence);

    heroBlock.appendChild(heroText);
    heroBlock.appendChild(badge);
    card.appendChild(heroBlock);

    (normalized.sections || []).forEach((section) => {
      const block = document.createElement("div");
      block.className = `ask-visual-section section-${section.type || "note"}`;

      const icon = document.createElement("div");
      icon.className = `ask-section-icon icon-${section.icon || section.type || "heart"}`;
      icon.textContent = iconSymbol(section.icon || section.type);

      const body = document.createElement("div");
      body.className = "ask-section-body";

      if (section.heading) {
        const heading = document.createElement("h4");
        heading.textContent = section.heading;
        body.appendChild(heading);
      }

      if (section.content) {
        const p = document.createElement("p");
        p.textContent = section.content;
        body.appendChild(p);
      }

      if (section.items && section.items.length) {
        const ul = document.createElement("ul");

        section.items.forEach((item) => {
          const li = document.createElement("li");

          if (typeof item === "string") {
            li.textContent = item;
          } else {
            const label = item.label || "";
            const text = item.text || "";

            if (label) {
              li.innerHTML = `<strong>${escapeHtml(label)}:</strong> ${escapeHtml(text)}`;
            } else {
              li.textContent = text;
            }
          }

          ul.appendChild(li);
        });

        body.appendChild(ul);
      }

      if (
        (section.pros && section.pros.length) ||
        (section.cons && section.cons.length) ||
        (section.watch_out && section.watch_out.length)
      ) {
        const tradeoffs = document.createElement("div");
        tradeoffs.className = "ask-tradeoff-grid";

        if (section.pros && section.pros.length) {
          tradeoffs.appendChild(renderMiniList("Pros", section.pros, "pros"));
        }

        if (section.cons && section.cons.length) {
          tradeoffs.appendChild(renderMiniList("Cons", section.cons, "cons"));
        }

        if (section.watch_out && section.watch_out.length) {
          tradeoffs.appendChild(renderMiniList("Watch out", section.watch_out, "watch"));
        }

        body.appendChild(tradeoffs);
      }

      block.appendChild(icon);
      block.appendChild(body);
      card.appendChild(block);
    });

    if (normalized.follow_up_questions && normalized.follow_up_questions.length) {
      const follow = document.createElement("div");
      follow.className = "ask-follow-up-box";

      const h = document.createElement("h4");
      h.textContent = "A few helpful questions";
      follow.appendChild(h);

      const ul = document.createElement("ul");

      normalized.follow_up_questions.forEach((question) => {
        const li = document.createElement("li");
        li.textContent = question;
        ul.appendChild(li);
      });

      follow.appendChild(ul);
      card.appendChild(follow);
    }

    if (normalized.gentle_reminder) {
      const reminder = document.createElement("p");
      reminder.className = "ask-gentle-reminder";
      reminder.textContent = normalized.gentle_reminder;
      card.appendChild(reminder);
    }

    return card;
  }

  function normalizeAssistantMessage(ai) {
    if (!ai || typeof ai !== "object") {
      return {
        layout_type: "quick",
        theme: "purple",
        confidence: "unclear",
        hero: {
          eyebrow: "BraveSprouts Guide",
          title: "Response",
          summary: String(ai || "")
        },
        sections: [],
        follow_up_questions: [],
        gentle_reminder: ""
      };
    }

    const hasNewHero = ai.hero && typeof ai.hero === "object";

    return {
      layout_type: ai.layout_type || "quick",
      theme: ai.theme || chooseTheme(ai.layout_type),
      confidence: ai.confidence || "unclear",
      hero: hasNewHero
        ? ai.hero
        : {
            eyebrow: "BraveSprouts Guide",
            title: ai.title || "Response",
            summary: ""
          },
      sections: normalizeSections(ai.sections || []),
      follow_up_questions: ai.follow_up_questions || [],
      gentle_reminder: ai.gentle_reminder || ""
    };
  }

  function normalizeSections(sections) {
    return sections.map((section) => {
      const type = section.type || inferSectionType(section.heading);
      const icon = section.icon || iconForType(type);

      return {
        type,
        icon,
        heading: section.heading || "",
        content: section.content || "",
        items: normalizeItems(section.items || []),
        pros: section.pros || [],
        cons: section.cons || [],
        watch_out: section.watch_out || []
      };
    });
  }

  function normalizeItems(items) {
    return items.map((item) => {
      if (typeof item === "string") {
        return item;
      }

      return {
        label: item.label || "",
        text: item.text || ""
      };
    });
  }

  function inferSectionType(heading) {
    const text = (heading || "").toLowerCase();

    if (text.includes("why") || text.includes("happens")) return "why";
    if (text.includes("do") || text.includes("try") || text.includes("can")) return "do";
    if (text.includes("avoid") || text.includes("watch")) return "avoid";
    if (text.includes("research") || text.includes("evidence") || text.includes("study")) return "research";
    if (text.includes("plan") || text.includes("step") || text.includes("week")) return "plan";
    if (text.includes("question") || text.includes("context")) return "question";
    if (text.includes("approach") || text.includes("option")) return "approach";

    return "note";
  }

  function iconForType(type) {
    const map = {
      why: "brain",
      do: "check",
      avoid: "x",
      research: "flask",
      approach: "compass",
      plan: "calendar",
      question: "question",
      note: "heart"
    };

    return map[type] || "heart";
  }

  function renderMiniList(title, items, type) {
    const box = document.createElement("div");
    box.className = `ask-mini-list mini-${type}`;

    const h = document.createElement("h5");
    h.textContent = title;
    box.appendChild(h);

    const ul = document.createElement("ul");

    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      ul.appendChild(li);
    });

    box.appendChild(ul);
    return box;
  }

  function confidenceLabel(confidence) {
    const labels = {
      high: "High confidence",
      moderate: "Moderate confidence",
      limited: "Limited evidence",
      unclear: "Context needed"
    };

    return labels[confidence] || "Context needed";
  }

  function iconSymbol(icon) {
    const icons = {
      brain: "⌘",
      check: "✓",
      x: "×",
      flask: "⌬",
      compass: "⌖",
      calendar: "◴",
      question: "?",
      heart: "♡",
      why: "⌘",
      do: "✓",
      avoid: "×",
      research: "⌬",
      approach: "⌖",
      plan: "◴",
      note: "♡"
    };

    return icons[icon] || "♡";
  }

  function chooseTheme(layoutType) {
    const themes = {
      comfort: "pink",
      quick: "purple",
      strategy: "green",
      explainer: "blue",
      plan: "orange",
      professional: "purple",
      clarifying: "yellow",
      comparison: "blue",
      research: "purple"
    };

    return themes[layoutType] || "purple";
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
  }

  function addMessage(role, content) {
    const message = document.createElement("div");
    message.className = `ask-message ask-message-${role}`;

    if (role === "bot" && typeof content === "object") {
      message.appendChild(renderBotCard(content));
    } else {
      message.textContent = content;
    }

    chatArea.appendChild(message);
    chatArea.scrollTop = chatArea.scrollHeight;
    return message;
  }

  function clearChat() {
    chatArea.innerHTML = "";
  }

  function setLoadingState(isLoading) {
    isSending = isLoading;
    form.classList.toggle("is-loading", isLoading);

    const sendButton = form.querySelector(".ask-send-btn");

    if (sendButton) {
      sendButton.disabled = isLoading;
      sendButton.textContent = isLoading ? "…" : "↑";
    }

    input.disabled = isLoading;
  }

  function parseAssistantMessage(content) {
    try {
      return normalizeAssistantMessage(JSON.parse(content));
    } catch {
      return {
        layout_type: "quick",
        theme: "purple",
        confidence: "unclear",
        hero: {
          eyebrow: "BraveSprouts Guide",
          title: "Response",
          summary: content
        },
        sections: [],
        follow_up_questions: [],
        gentle_reminder: ""
      };
    }
  }

  async function loadConversations() {
    try {
      const response = await fetch("/api/ask-bravesprouts/conversations");
      const data = await response.json();

      if (!response.ok || !data.success) {
        historyList.innerHTML = `<p class="ask-history-empty">Could not load chats.</p>`;
        return;
      }

      const conversations = data.conversations || [];

      if (!conversations.length) {
        historyList.innerHTML = `<p class="ask-history-empty">No chats yet.</p>`;
        return;
      }

      historyList.innerHTML = "";

      conversations.forEach((conversation) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "ask-history-item";

        if (conversation.conversation_id === currentConversationId) {
          item.classList.add("active");
        }

        item.innerHTML = `
          <span class="ask-history-title">${escapeHtml(conversation.title || "New conversation")}</span>
          <span class="ask-history-date">${formatDate(conversation.updated_at)}</span>
        `;

        item.addEventListener("click", () => {
          loadConversation(conversation.conversation_id);
          closeSidebar();
        });

        historyList.appendChild(item);
      });
    } catch (error) {
      console.error("Conversation load error:", error);
      historyList.innerHTML = `<p class="ask-history-empty">Could not load chats.</p>`;
    }
  }

  async function loadConversation(conversationId) {
    try {
      const response = await fetch(`/api/ask-bravesprouts/conversations/${conversationId}`);
      const data = await response.json();

      if (!response.ok || !data.success) {
        return;
      }

      currentConversationId = conversationId;
      clearChat();
      askPage.classList.add("chat-started");

      (data.messages || []).forEach((message) => {
        if (message.role === "user") {
          addMessage("user", message.content);
        } else {
          addMessage("bot", parseAssistantMessage(message.content));
        }
      });

      chatArea.scrollTop = chatArea.scrollHeight;
      input.focus();
    } catch (error) {
      console.error("Conversation open error:", error);
    }
  }

  function startNewChat() {
    currentConversationId = null;
    clearChat();
    askPage.classList.remove("chat-started");
    input.value = "";
    autoResizeInput();
    input.focus();
    closeSidebar();
  }

  function formatDate(dateString) {
    if (!dateString) return "";

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric"
    });
  }

  async function sendQuestion(question) {
    if (isSending) return;

    askPage.classList.add("chat-started");

    addMessage("user", question);

    const loadingMessage = addMessage("bot", "Thinking...");
    setLoadingState(true);

    try {
      const response = await fetch("/api/ask-bravesprouts/message", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: question,
          conversation_id: currentConversationId
        })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        loadingMessage.textContent =
          data.error || "Something went wrong. Please try again.";
        return;
      }

      currentConversationId = data.conversation_id;

      loadingMessage.innerHTML = "";
      loadingMessage.appendChild(renderBotCard(data.message));

      loadConversations();
    } catch (error) {
      console.error("Ask BraveSprouts fetch error:", error);
      loadingMessage.textContent =
        "I’m having trouble responding right now. Please try again.";
    } finally {
      setLoadingState(false);
      input.focus();
    }
  }

  suggestionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const question = button.dataset.question || button.textContent.trim();
    input.value = question;
    autoResizeInput();
    input.focus();
  });
});

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = input.value.trim();

    if (!question || isSending) {
      input.focus();
      return;
    }

    input.value = "";
    autoResizeInput();
    await sendQuestion(question);
  });

  historyToggle.addEventListener("click", toggleSidebar);
  historyClose.addEventListener("click", closeSidebar);
  newChatButton.addEventListener("click", startNewChat);

  if (plusButton) {
    plusButton.addEventListener("click", startNewChat);
    plusButton.setAttribute("aria-label", "New chat");
  }

  loadConversations();
});