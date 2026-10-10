FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && useradd --create-home --uid 10001 sticker

COPY --chown=sticker:sticker . .

USER sticker

EXPOSE 8765

CMD ["python", "server.py"]

