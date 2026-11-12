FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Creating a non-root user
RUN useradd -m appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Change the file owner and switch to the new user
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]