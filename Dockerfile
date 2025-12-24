FROM python:3.9

# Set the working directory to /app
WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Set display port for headless mode
ENV DISPLAY=:99 

# Install dependencies for Chrome and WebDriver
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    xvfb \
    libxi6 \
    libnss3 \
    libxss1 \
    libgtk-3-0 \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    && apt-get clean

# Install Chrome (headless version)
RUN wget https://mirror.cs.uchicago.edu/google-chrome/pool/main/g/google-chrome-stable/google-chrome-stable_114.0.5735.198-1_amd64.deb && \
    apt-get install -y ./google-chrome-stable_114.0.5735.198-1_amd64.deb && \
    rm google-chrome-stable_114.0.5735.198-1_amd64.deb

# Install ChromeDriver
RUN CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    wget -N https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    rm chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver

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
