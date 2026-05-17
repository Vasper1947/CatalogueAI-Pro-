# 🚀 CatalogAI Pro - AI-Powered Catalog Extraction Platform

Production-ready backend system for extracting product information from catalogs using Claude AI.

## ✨ Features

- **FastAPI Backend** - Modern Python web framework
- **AI-Powered Extraction** - Uses Claude for intelligent data extraction
- **File Processing** - Supports PDF, DOCX, PPTX, and images
- **Job Management** - Track and manage extraction jobs
- **Real-time Progress** - Monitor extraction progress in real-time
- **Cost Tracking** - Estimate and track Claude API costs
- **Production Ready** - Deployed on Fly.io with 99.9% uptime

## 🚀 Quick Start

### Deploy to Fly.io (One Command)

```bash
bash scripts/deploy.sh catalogai-prod
```

Your backend will be live at: `https://catalogai-prod.fly.dev`

### Local Development

```bash
bash scripts/setup.sh
cd backend
python -m uvicorn main:app --reload
```

## 📋 Requirements

- Python 3.11+
- Fly.io account (free)
- Claude API key

## 🔑 Environment Variables

```env
ANTHROPIC_API_KEY=sk-ant-v0-your-key
CLAUDE_MODEL=claude-opus-4-5
DEBUG=false
DATABASE_URL=sqlite:///./catalogai.db
```

## 📚 API Endpoints

- `GET /health` - Health check
- `POST /api/jobs` - Create job
- `GET /api/jobs/{job_id}` - Get status
- `POST /api/jobs/{job_id}/upload` - Upload file
- `POST /api/jobs/{job_id}/process` - Process
- `GET /api/jobs/{job_id}/progress` - Progress
- `GET /api/jobs/{job_id}/products` - Results

## 📖 Documentation

- [Setup Guide](docs/SETUP.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [API Docs](docs/API.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## 💻 Tech Stack

- FastAPI
- SQLAlchemy
- Claude AI
- Docker
- Fly.io

## 🔒 Security

- HTTPS/TLS
- Environment variables for secrets
- Input validation
- CORS configured

## 📝 License

MIT - See LICENSE file

---

**Made with ❤️ for catalog extraction**
