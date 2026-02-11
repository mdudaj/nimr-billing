FROM python:3.9

# Set the working directory to /app
WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy the wait-for-it.sh script into the container
COPY wait-for-it.sh /usr/wait-for-it.sh
RUN chmod +x /usr/wait-for-it.sh

# Expose port 8000 for Django or Gunicorn
EXPOSE 8000

# Running migrations
# RUN /usr/wait-for-it.sh db:5432 -- python manage.py migrate

# Command to run the application with Gunicorn
CMD ["gunicorn", "--config", "gunicorn-cfg.py", "core.wsgi"]
