FROM python:3.12-slim
WORKDIR /srv
# The base image's pip lags behind and carries its own advisories (pip-audit).
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Unprivileged user: if the app is ever compromised, the attacker isn't root in the container.
RUN useradd --create-home --uid 10001 app
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
