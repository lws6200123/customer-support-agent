# DemoShop Customer Support Operations Console

Vue 3 + TypeScript + Vite frontend for the Customer Support Ticket Agent portfolio project.

The browser communicates only with the Stage 6 FastAPI service. It never receives or calls DeepSeek or RAGFlow credentials directly.

```bash
cp .env.example .env.local
npm ci
npm run dev
```

Visit `http://localhost:5173`. Keep the FastAPI service running at the configured `VITE_API_BASE_URL`.
