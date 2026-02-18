# Simple Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install requests python-dotenv

# Copy your game builder
COPY main.py .
COPY users.json .

# Run the game builder
CMD ["python", "main.py"]