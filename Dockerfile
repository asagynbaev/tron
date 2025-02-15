# Use official Python image
FROM --platform=linux/amd64 python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Gunicorn explicitly
RUN pip install gunicorn

# Copy the project files
COPY . .

# Run migrations and collect static files
RUN python manage.py migrate --noinput
RUN mkdir -p staticfiles
RUN python manage.py collectstatic --noinput

# Expose port 8000
EXPOSE 8000

# Start the app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "core.wsgi:application"]