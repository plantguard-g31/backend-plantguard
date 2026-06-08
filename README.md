# 🌱 PlantGuard Backend API

**Server-side infrastructure for  plant disease diagnosis targeting smallholder farmers in rural Nepal.**

## 🏗️ Architecture Overview
| Layer | Technology | Purpose |
|-------|------------|---------|
| **API Framework** | FastAPI + Uvicorn | Async, high-concurrency REST endpoints |
| **Database** | PostgreSQL 15 + Alembic | ACID-compliant schema, version-controlled migrations |
| **Authentication** | PyJWT + bcrypt | Stateless token auth, irreversible password hashing |
| **Security** | Magic byte validation, rate limiting, audit logging | Defense-in-depth input defense (CWE-434, DoS prevention) |
| **Diagnostic Pipeline** | OpenCV + Severity Routing + Bilingual Resolver | Quality gate → AI inference → severity-aware treatment → EN/NE localization |


# Project Structure
app/
├── api/v1/          # Auth & Diagnosis endpoints
├── core/            # Config, JWT, dependencies, logging
├── db/              # SQLAlchemy models & async session
├── middleware/      # Rate limit, magic bytes, bilingual errors
├── services/        # Quality gate, analytics, treatment mapping, localization
└── schemas/         # Pydantic request/response validation

## 🚀 Quick Start (Development)
```bash
# 1. Clone & setup
git clone https://github.com/YOUR_USERNAME/plantguard_backend.git
cd plantguard_backend
python -m venv venv
source venv/Scripts/activate  # Git Bash / Linux
# .\venv\Scripts\Activate.ps1  # PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials & JWT secret

# 4. Run migrations
alembic upgrade head

# 5. Start server
uvicorn app.main:app --reload