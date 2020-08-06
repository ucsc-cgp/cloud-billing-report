FROM perl:5.30.2

# Hardcoded into script
RUN mkdir -p /root/gcp-reporting/
WORKDIR /root/gcp-reporting/
RUN ln -s /bin/date /usr/bin/date

# Use wait-for-it.sh to delay running the script until MySQL has started and is
# healthy. Otherwise, the script will fail repeatedly trying to connect to the
# database then loiter around aimlessly after it runs successfully.
RUN curl -o /wait-for-it.sh https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh
RUN chmod +x /wait-for-it.sh

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

CMD ["/wait-for-it.sh", "db:3306", "-t", "0", "--", "perl", "report_gcp_spending"]
