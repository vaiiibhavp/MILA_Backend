# Dockerfile for Python/FastAPI
 
FROM python:3.11-slim
 
# Set working directory inside the container
WORKDIR /app
 
# Copy requirements file first (for better caching)
COPY requirements.txt .
 
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy all files from host to container
COPY . .
 
# Expose port (default 8000, can be overridden)
EXPOSE 3000
 
# Start app with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
