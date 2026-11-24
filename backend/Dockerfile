FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
FROM python:3.12-slim
COPY --from=build /install /usr/local
WORKDIR /app
COPY main.py .
RUN mkdir -p /data
ENV PYTHONUNBUFFERED=1 LITELLM_LOCAL_MODEL_COST_MAP=True
EXPOSE 8000
CMD ["sh","-c","exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
