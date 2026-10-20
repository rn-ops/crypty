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
