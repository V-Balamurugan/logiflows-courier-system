# LogiFlows - Deployment & DevOps Guide

## 1. Quickstart with Docker Compose

LogiFlows provides a fully containerized stack including the FastAPI backend, React Vite frontend, PostgreSQL database, and automated migrations.

### Prerequisites
- Docker Engine >= 24.0
- Docker Compose v2

### Launching the Stack
1. Clone the repository and navigate to the project directory:
   ```bash
   cd "logiflows courier site"
   ```
2. Copy environment file:
   ```bash
   cp .env.example .env
   ```
3. Build and launch all containers:
   ```bash
   docker compose up --build -d
   ```
4. Verify running services:
   ```bash
   docker compose ps
   ```

The application will be accessible at:
- **Frontend Web Portal:** `http://localhost:5173` (or `http://localhost:3000` in production)
- **FastAPI OpenAPI Swagger:** `http://localhost:8000/docs`
- **PostgreSQL Database:** `localhost:5432`

---

## 2. Production Hardening Checklist
- Replace default `SECRET_KEY` with a cryptographically secure 64-character token.
- Enable HTTPS with Let's Encrypt / reverse proxy (Nginx or Traefik).
- Configure SMTP/Brevo credentials for outgoing automated customer emails.
- Set PostgreSQL volume backups on a daily cron schedule.

