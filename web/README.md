# OfficeAgent Web

Next.js chat UI for local validation of authentication, `user_id`, `session_id`, conversation history, Memory and LangGraph Persistence.

## Start

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

The frontend defaults to `http://127.0.0.1:8000/api/v1`. Override it with:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run dev
```

Start the FastAPI backend and PostgreSQL infrastructure before using the chat UI.
