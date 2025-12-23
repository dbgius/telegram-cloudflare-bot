FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot.py .

# Expose port
EXPOSE 8080

# Environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV BOT_TOKEN="8278734441:AAEqPI3swV6L0aLTncKXEA_ivvYOFM3zhz8"
ENV ADMIN_CHAT_IDS="7853409680"
ENV WALLET_USDT_TRC20="TXYZabc123..."
ENV WALLET_USDT_BEP20="0xABCdef456..."

# Run the application
CMD ["python", "bot.py"]
