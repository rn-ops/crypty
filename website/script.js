const menuBtn = document.getElementById("menuBtn");
const nav = document.getElementById("nav");

menuBtn?.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  menuBtn.setAttribute("aria-expanded", String(open));
});

nav?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    nav.classList.remove("open");
    menuBtn?.setAttribute("aria-expanded", "false");
  });
});

// Concept demo only: this form never sends or stores the entered email.
const form = document.getElementById("interestForm");
const email = document.getElementById("email");
const note = document.getElementById("formNote");

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!email?.checkValidity()) {
    email?.reportValidity();
    return;
  }
  note.textContent = "THANK YOU — DEMO ONLY. NO DATA WAS SENT.";
  note.style.fontWeight = "500";
  email.value = "";
});

const chatLauncher = document.getElementById("chatLauncher");
const chatPanel = document.getElementById("chatPanel");
const chatClose = document.getElementById("chatClose");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");
const chatHistory = [];
let chatPending = false;

function setChatOpen(open) {
  chatPanel.hidden = !open;
  chatLauncher.setAttribute("aria-expanded", String(open));
  if (open) chatInput.focus();
}

function addChatMessage(text, role, isError = false) {
  const article = document.createElement("article");
  article.className = `chat-message ${role === "user" ? "user-message" : "bot-message"}${isError ? " chat-error" : ""}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "YOU" : isError ? "CONNECTION" : "CRYPTY GUIDE";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  article.append(label, paragraph);
  chatMessages.append(article);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return article;
}

chatLauncher?.addEventListener("click", () => setChatOpen(chatPanel.hidden));
chatClose?.addEventListener("click", () => setChatOpen(false));

chatForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (chatPending) return;
  const question = chatInput.value.trim();
  if (!question) return;

  addChatMessage(question, "user");
  chatInput.value = "";
  const submitButton = chatForm.querySelector("button[type='submit']");
  chatPending = true;
  chatInput.disabled = true;
  submitButton.disabled = true;
  const pending = addChatMessage("Thinking…", "model");
  try {
    if (window.location.protocol === "file:") {
      throw new Error("Chat needs the local website server. Run `python website/bot/server.py` from the project folder, then open http://127.0.0.1:8000.");
    }
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: chatHistory.slice(-8) }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The assistant could not answer right now.");
    pending.remove();
    addChatMessage(result.reply, "model");
    chatHistory.push({ role: "user", text: question }, { role: "model", text: result.reply });
  } catch (error) {
    pending.remove();
    addChatMessage(error.message || "Could not reach the assistant. Please try again.", "model", true);
  } finally {
    chatPending = false;
    chatInput.disabled = false;
    submitButton.disabled = false;
    chatInput.focus();
  }
});

chatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
