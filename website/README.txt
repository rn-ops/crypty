Crypty website
==============

Purpose
-------
This directory contains a static product-concept/marketing site and an
optional local chat endpoint. It is not the desktop workstation, and its
mock dashboard, metrics, plans, and architecture are not evidence that those
capabilities are shipped. Keep public statements aligned with tested product
behavior.

Run locally
-----------
Static page only:
  Open index.html in a browser.

Site with the optional chat service:
  1. Install Python 3.9 or newer.
  2. Set XAI_API_KEY in the server environment. Never put it in browser code,
     HTML, or a committed file.
  3. From the repository root, run:
       py -3 website\bot\server.py
  4. Open http://127.0.0.1:8000.

The default server binds to localhost. The chat endpoint uses the xAI API;
requests may incur charges. XAI_MODEL can select a model available to the
configured account. Keep keys out of logs and do not send evidence, recovered
file contents, credentials, or other sensitive data to the chatbot.

Current limitations
-------------------
- The interest/contact form is front-end demo behavior; it does not submit or
  store contact information.
- The dashboard and product metrics are illustrative demo data.
- Plans, centralized audit services, licensing, and account features shown
  on the page are not necessarily implemented or available.
- The chat is optional and depends on a local server and external API access.
- Fonts are loaded from Google Fonts when online; local system fallbacks are
  provided.

Before a public launch
----------------------
- Verify every product, security, recovery, sanitization, pricing, and
  availability claim against a released and tested capability.
- Either connect the interest form to an approved backend with consent,
  privacy, spam protection, and secure handling, or retain the demo-only
  disclosure.
- Publish support, privacy, security-contact, and product-limitation
  information.
- Keep the chatbot separate from evidence workflows, with clear disclosures
  and a non-AI contact path.
