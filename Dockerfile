FROM python:3.8.6-slim
LABEL org.opencontainers.image.source https://github.com/ucsc-cgp/cloud-billing-report

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY main.py .
COPY src/ src/
RUN mkdir -p tmp/emails/

ENTRYPOINT ["python3", "main.py"]
