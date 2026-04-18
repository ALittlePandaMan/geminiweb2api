FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY gemini_webapi ./gemini_webapi
COPY cli.py README.md ./

EXPOSE 9090

CMD ["python", "-m", "uvicorn", "gemini_webapi.openai_server.app:app", "--host", "0.0.0.0", "--port", "9090"]
