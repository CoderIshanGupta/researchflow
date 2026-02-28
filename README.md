# 🧠 ResearchFlow

ResearchFlow is a research-focused AI platform that helps researchers manage academic papers, analyze them using AI, and generate research outputs within persistent research sessions.

All AI interactions (chat, summaries, drafts, and references) are strictly limited to the papers added by the user to ensure source-grounded and reproducible results.

---

## ✨ Core Features

### 📌 Research Sessions
- Create sessions using a research topic and title  
- Sessions persist until manually deleted  
- All data (sources, chat, drafts) is session-scoped  

### 📚 Paper Management
- Add suggested or searched research papers  
- Upload user-created PDF papers  
- Remove or replace papers at any time  
- All added papers act as the session’s knowledge base  

### 💬 AI Chat (Source-Restricted)
- Chat with AI using only session papers  
- No external or hallucinated context  
- Chat history is saved per session  
- Chat sessions can be downloaded  

### 📝 AI Draft Generation
- Generate:
  - Literature reviews  
  - Research summaries  
- Drafts are generated only from added papers  
- Drafts are editable and downloadable  

### 🔖 Reference Generation
- Generate citations from session papers  
- Supported formats:
  - BibTeX  
  - APA  
  - MLA  
  - IEEE  

### 📊 Research Metrics
- Visual comparison of added papers  
- Metrics include:
  - Relevance score  
  - Citation count  
  - Keyword hits  

---

## 🛠️ Tech Stack

### 🎨 Frontend
- Next.js (App Router)  
- React + TypeScript  
- Tailwind CSS  
- Framer Motion  
- Zustand  
- Recharts  

### ⚙️ Backend
- FastAPI (Python)  
- REST-based APIs  
- Session-based persistence  

### 🔐 Authentication & Storage
- Supabase  
  - User authentication  
  - PDF file uploads  

### 🤖 AI
- Retrieval-Augmented Generation (RAG)  
- Context strictly limited to session papers  

---

## 📁 Project Structure

```
.
├── frontend/
│   ├── app/
│   ├── components/
│   ├── store/
│   └── lib/
│
├── backend/
│   ├── routes/
│   ├── services/
│   ├── models/
│   ├── main.py
│   └── requirements.txt
│
└── README.md
```

---

## 🚀 Getting Started

### ⬇️ Clone the Repository

```bash
git clone https://github.com/CoderIshanGupta/researchflow.git
cd researchflow
```

---

## 🔧 Environment Setup

### 🌐 Frontend

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

---

### 🧩 Backend

If required, create `backend/.env`:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

---

## ▶️ Running the Project

### 🖥️ Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend runs at: http://localhost:8000

---

### 🌍 Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:3000

---

## 🎯 Current Scope

- Single-user research sessions  
- Persistent sessions and chat history  
- No real-time collaboration  
- No multi-user shared sessions  

---

## ⚠️ Notes

This project is designed to assist academic research workflows.  
All AI-generated content should be reviewed before use in formal research.

---

## 📄 License

This project is currently under active development.
