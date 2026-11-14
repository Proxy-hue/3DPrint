FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Creating a user
RUN useradd -m appuser

# Build argument: install only production dependencies by default
ARG INSTALL_DEV=false

COPY requirements.txt .
COPY requirements-dev.txt .

# If INSTALL_DEV=true, we install test libraries, otherwise only development
RUN if [ "$INSTALL_DEV" = "true" ] ; then pip install --no-cache-dir -r requirements-dev.txt ; else pip install --no-cache-dir -r requirements.txt ; fi

COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]