FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for OpenCV, Tesseract, etc.
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies (skipping cache to save container space)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Cloud Run needs the app to listen on 0.0.0.0 and the PORT env variable
ENV PORT=8080

# Start Uvicorn
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
