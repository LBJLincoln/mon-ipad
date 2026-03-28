FROM python:3.11-slim

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 for Paperclip CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g pnpm

# Install Paperclip CLI
RUN npx paperclipai onboard --yes 2>/dev/null || echo "Paperclip CLI installed"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /tmp

# Create non-root user for HF
RUN useradd -m -u 1000 user
USER user

EXPOSE 7860
ENV PORT=7860
ENV GRADIO_SERVER_NAME=0.0.0.0

CMD ["python", "app.py"]
