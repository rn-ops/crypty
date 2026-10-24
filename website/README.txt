CRYPTY — DARK PROFESSIONAL / RESTRAINED NEO-BRUTALIST WEBSITE
==============================================================

This is a static concept website for the Crypty data recovery, sanitization,
and auditability platform.

DESIGN DIRECTION
- Mostly dark charcoal and slate surfaces
- Restrained acid-lime accent with muted amber for status
- Professional spacing and typography
- Neo-brutalist details limited to hard-edged buttons, subtle offset shadows,
  strong section headings, and a few high-contrast elements

RUN THE WEBSITE AND CHAT
1. Install Python 3.9 or newer.
2. Set XAI_API_KEY in your environment. Create an API key in the xAI Console at console.x.ai.
3. From the repository root, run: python website/bot/server.py
4. Open http://127.0.0.1:8000 in your browser.

The website itself remains static. The local Python server serves the files and
provides /api/chat; the xAI key stays on the server and is never sent to the
browser. The default model is grok-4.7. Set XAI_MODEL to use another model
available to your API account. If no key is configured, the page still loads
and chat reports the setup issue.

xAI API requests are billed per token and require API credits or billing. The
free Grok app plan does not include free API requests. Check current model
pricing and your team's usage limits in the xAI Console.

To view only the static page without chat, open index.html directly.

NOTES
- The product dashboard uses illustrative demo data.
- The contact form is front-end only and does not send or store submissions.
- The chat requires the local Python server and an xAI API key.
- No authentication, payments, or live audit synchronization is connected.
- Google Fonts are loaded online; system fallbacks are included.

FILES
- index.html
- styles.css
- script.js
- README.txt
