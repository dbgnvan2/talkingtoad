# Orchestrator

The orchestrator is the central coordination service that manages workflow execution, task distribution, and system integration.

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd orchestrator
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Create a `.env` file in the orchestrator directory with the following variables:

```env
ORCHESTRATOR_HOST=0.0.0.0
ORCHESTRATOR_PORT=8000
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///orchestrator.db
```

## Running the Orchestrator

### Development Mode

```bash
python main.py
```

Or with hot-reload (if using uvicorn):
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Docker Deployment

Build and run using Docker:

```bash
docker build -t orchestrator .
docker run -p 8000:8000 orchestrator
```

## API Endpoints

Once running, access the API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Testing

Run tests with:

```bash
pytest tests/
```

## Project Structure

```
orchestrator/
├── main.py              # Entry point
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── .env                # Environment variables
├── tests/              # Test directory
└── README.md           # This file
```

## Troubleshooting

- **Port already in use**: Change the port in `.env` or use `kill -9 $(lsof -t -i:8000)`
- **Dependencies not found**: Run `pip install -r requirements.txt` again
- **Database errors**: Delete `orchestrator.db` and restart

## Support

For issues or questions, please open an issue in the repository.
