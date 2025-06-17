FROM python:3.10-slim

# Create a non-root user for Spaces (UID 1000 is the default)
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make sure cache directories exist and are writable by non-root user
RUN mkdir -p /tmp/huggingface && chown -R user:user /tmp/huggingface

# Environment variables must be set before any Python code runs
ENV HF_HOME=/tmp/huggingface \
    HF_DATASETS_CACHE=/tmp/huggingface/datasets \
    HUGGINGFACE_HUB_CACHE=/tmp/huggingface/hub \
    TRANSFORMERS_CACHE=/tmp/huggingface/transformers \
    XDG_CACHE_HOME=/tmp/huggingface \
    PYTHONUNBUFFERED=1
USER user
WORKDIR /app

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
