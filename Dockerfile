FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Ensure migrations directory exists
RUN mkdir -p migrations

# Run the bot
# Note: In production without Docker, use bot_manager.sh for process management
CMD ["python", "-u", "main.py"]