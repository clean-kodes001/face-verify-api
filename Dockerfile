FROM ubuntu:22.04

# Install system dependencies
RUN apt update && apt install software-properties-common -y \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt update \
    && apt install -y \
        python3.10 \
        python3.10-distutils \
        python3.10-dev \
        curl \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        libatlas-base-dev \
    && apt autoremove -y \
    && apt-get clean

# Install pip for Python 3.10
RUN curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3.10 get-pip.py \
    && rm get-pip.py

# Upgrade pip
RUN pip install --upgrade pip

# Set working directory
WORKDIR /app

# Copy everything from your root to /app/
COPY . /app/

# Install Python dependencies with --ignore-installed flag
RUN pip install --ignore-installed --no-cache-dir -r requirements.txt

# Set environment variables
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Run with Gunicorn (production)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]