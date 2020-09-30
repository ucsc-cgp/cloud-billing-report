FROM perl:5.30.2
ENV TZ America/Los_Angeles
RUN mkdir -p /root/aws-reporting/
WORKDIR /root/aws-reporting/
COPY cpanfile /root/aws-reporting/
RUN cpanm --installdeps .
COPY report_aws_spending /root/aws-reporting/
ENTRYPOINT ["perl", "report_aws_spending"]
