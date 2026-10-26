# Crypty website and account API

The Next.js website is in this folder. The Flask account API and its SQLite
database are in the repository's `auth/api/` directory.

## Run

1. Install the API dependencies from the repository root:

   ```powershell
   pip install -r ..\auth\api\requirements.txt
   ```

2. Set `SECUREFORENSICS_JWT_SECRET` and `CRYPTY_SERVICE_KEY` in the API
   process environment. Set the same `CRYPTY_SERVICE_KEY` in a local copy of
   `.env.local.example` named `.env.local`; set `AUTH_API_URL` if the API is
   not listening at `http://127.0.0.1:5000`.

3. From this folder, start the services in separate terminals:

   ```powershell
   npm install
   npm run auth
   npm run dev
   ```

The website offers plan selection and account creation. Audit logs at `/audit`
require an admin or auditor account. Bootstrap an admin from
`..\auth\api\` with `python create_first_admin.py admin1 "your-long-password"`.
The API owns the shared case and hash-chained audit database.
