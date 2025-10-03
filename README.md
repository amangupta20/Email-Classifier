# Intelligent Inbox Email Classification System

An AI-powered email classification system that automatically categorizes and prioritizes your emails using machine learning and natural language processing.

## 🚀 Features

- **Smart Classification**: Automatically categorize emails into predefined classes (e.g., Work, Personal, Promotions, Urgent)
- **Real-time Processing**: Process emails as they arrive
- **Machine Learning**: Uses advanced ML models for accurate classification
- **Dashboard**: Web-based dashboard for monitoring and managing classifications
- **API-Driven**: RESTful API for integration with email clients
- **Scalable Architecture**: Built with FastAPI and React for high performance

## 🛠 Tech Stack

### Backend

- **Python 3.11+** with type hints and async/await
- **FastAPI** for high-performance API development
- **SQLAlchemy** for database ORM
- **Pydantic** for data validation
- **Celery** for background task processing
- **Redis** for caching and message queuing

### Frontend

- **React 18** with TypeScript
- **shadcn/ui** for modern UI components
- **Tailwind CSS** for styling
- **Redux Toolkit** for state management
- **Axios** for API communication

### Infrastructure

- **Docker & Docker Compose** for containerization
- **PostgreSQL** for data persistence
- **Redis** for caching

## 📁 Project Structure

```
email-classifier/
├── backend/                 # Python FastAPI backend
│   ├── app/                # Main application code
│   ├── tests/              # Backend tests
│   ├── pyproject.toml      # Python project configuration
│   └── Dockerfile          # Backend container config
├── frontend/               # React frontend application
│   ├── src/                # Source code
│   ├── public/             # Static assets
│   ├── package.json        # Node.js project configuration
│   └── Dockerfile          # Frontend container config
├── docker-compose.yml       # Container orchestration
└── .env.example            # Environment variables template
```

## 🏁 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for local development)

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd email-classifier
   ```

2. **Environment Setup**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start with Docker Compose**

   ```bash
   docker-compose up --build
   ```

   The application will be available at:

   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Local Development

**Backend Setup:**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

**Frontend Setup:**

```bash
cd frontend
npm install
npm start
```

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 📚 API Documentation

Once the backend is running, visit http://localhost:8000/docs for interactive API documentation.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support, email support@email-classifier.com or create an issue in this repository.

---

**Built with ❤️ for better email management**
