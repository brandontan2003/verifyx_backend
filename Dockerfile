FROM python:3.12.13-slim-trixie

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip==26.1  \
    && pip install --no-cache-dir --upgrade -r requirements.txt  \
    && pip uninstall -y ecdsa

ENV PYTHONPATH /app

ENTRYPOINT ["fastapi", "run", "app/main.py", "--port", "8000"]