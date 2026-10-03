FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/app \
    DATA_DIR=/data \
    VERIFACE_AUTOSTART=1

# build-essential: insightface compiles a small Cython extension
# libglib2.0-0 / libxcb1 / libsm6 / libxext6 / libxrender1 / libgomp1: runtime deps of OpenCV and ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libglib2.0-0 libgl1 libgomp1 libxcb1 libsm6 libxext6 libxrender1 curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app && mkdir -p /data /app && chown app:app /data /app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

USER app

# Bake the face model into the image so first start needs no internet and no wait
RUN python -c "from insightface.app import FaceAnalysis; \
FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider']).prepare(ctx_id=0, det_size=(320, 320))"

COPY --chown=app:app . .

RUN SECRET_KEY=build DATA_DIR=/tmp/build python manage.py collectstatic --noinput

VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -fs http://localhost:8000/healthz || exit 1

ENTRYPOINT ["docker/entrypoint.sh"]
