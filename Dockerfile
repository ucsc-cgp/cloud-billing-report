FROM python:3.8.6-slim
LABEL org.opencontainers.image.source https://github.com/ucsc-cgp/cloud-billing-report

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source files
COPY __init__.py .
COPY main.py .
COPY src/ src/

# Create directory to write data to
RUN mkdir -p data/

ENTRYPOINT ["python3", "main.py"]
