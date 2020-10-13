FROM python:3.8.6-slim
LABEL maintainer="natanlao@users.noreply.github.com"

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY templates/ templates/
COPY report.py .

ENTRYPOINT ["python", "report.py"]