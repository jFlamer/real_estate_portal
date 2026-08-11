# Smart RE Listings

scraping → mormalisation → filtered search + chat with intent parsing (LLM).

## Quick start

```
cp .env.example .env      # insert Gemini API key
docker compose up -d mysql
cd backend && uv sync && uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Backend: http://localhost:8000 · Frontend: http://localhost:5173

Project reasoning descr: [REASONING.md](REASONING.md)