FROM perl:5.30.2

# Hardcoded into script
RUN mkdir -p /root/gcp-reporting/
WORKDIR /root/gcp-reporting/
RUN ln -s /bin/date /usr/bin/date

# Install dependencies
COPY cpanfile /root/gcp-reporting/
RUN cpan install cpanm
RUN cpanm --installdeps .
# gsutil is required to run the script
RUN curl https://dl.google.com/dl/cloudsdk/release/google-cloud-sdk.tar.gz > /tmp/google-cloud-sdk.tar.gz
RUN tar -C /root -xvf /tmp/google-cloud-sdk.tar.gz && /root/google-cloud-sdk/install.sh --quiet

# Install script and config
COPY config.pl /root/gcp-reporting/
COPY report_gcp_spending /root/gcp-reporting/
COPY gcloud/ /root/gcloud/
ENV CLOUDSDK_CONFIG /root/gcloud

CMD ["perl", "report_gcp_spending"]
