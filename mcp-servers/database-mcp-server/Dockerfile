FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8000

CMD ["python", "server.py"]
