FROM perl:5.30.2
ENV TZ America/Los_Angeles

# Hardcoded into script
RUN mkdir -p /root/gcp-reporting/
WORKDIR /root/gcp-reporting/

# gsutil is required to run the script
RUN curl https://dl.google.com/dl/cloudsdk/release/google-cloud-sdk.tar.gz > /tmp/google-cloud-sdk.tar.gz
RUN tar -C /root -xvf /tmp/google-cloud-sdk.tar.gz && /root/google-cloud-sdk/install.sh --quiet

# Install dependencies
COPY cpanfile /root/gcp-reporting/
RUN cpanm --installdeps .

# Install script and config
COPY report_gcp_spending /root/gcp-reporting/

ENTRYPOINT ["perl", "report_gcp_spending"]
