FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 中文字体：导出 Word / 生成 PDF 都要用
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk curl && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY apps/api ./apps/api
COPY apps/web/dist ./apps/web/dist

ENV PYTHONPATH=/app/apps/api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://127.0.0.1:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
