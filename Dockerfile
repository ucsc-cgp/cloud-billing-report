FROM python:3.8.6-slim
LABEL maintainer="natanlao@users.noreply.github.com"
LABEL org.opencontainers.image.source https://github.com/ucsc-cgp/cloud-billing-report

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY templates/ templates/
COPY report.py .
COPY src/ src/
COPY scripts/ scripts/
RUN chmod +x scripts/send_personalized_emails.sh
RUN mkdir -p tmp/personalizedEmails/

ENTRYPOINT ["python", "report.py"]