# Multi-stage Docker build for React + FastAPI application
# Stage 1: Build the React frontend
FROM node:18-alpine AS frontend-builder

# Set working directory for frontend build
WORKDIR /app/frontend

# Copy frontend source code
COPY frontend/ .

# Install frontend dependencies
RUN npm install

# Build the React application for production
# This creates an optimized dist/ folder with minified assets
RUN npm run build

# Stage 2: Setup Python backend and serve the built frontend
FROM python:3.10-slim AS backend

# Set working directory for the application
WORKDIR /app

# Copy Python requirements first (for better Docker layer caching)
COPY backend/requirements.txt ./

# Install Python dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get purge -y --auto-remove && \
    rm -rf /var/lib/apt/lists/*

# Rebuild
RUN pip install git+https://github.com/MolecularFoundryCrucible/pycrucible@e7040ae
RUN pip install --no-cache-dir -r requirements.txt


# Copy backend source code
COPY backend/ ./

# Copy backend and built frontend
COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./static

# Expose port 8000
EXPOSE 8000

# Start the FastAPI server
# --host 0.0.0.0 allows external connections (required for containers)
# --port 8000 matches the exposed port
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"] 
