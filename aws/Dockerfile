FROM perl:5.30.2
RUN mkdir -p /root/aws-reporting/
WORKDIR /root/aws-reporting/
# Use wait-for-it.sh to delay running the script until MySQL has started and is
# healthy. Otherwise, the script will fail repeatedly trying to connect to the
# database then loiter around aimlessly after it runs successfully.
RUN curl -o /wait-for-it.sh https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh
RUN chmod +x /wait-for-it.sh
COPY cpanfile /root/aws-reporting/
RUN cpanm --installdeps .
COPY report_aws_spending /root/aws-reporting/
COPY config.pl /root/aws-reporting/
ENV REPORT_DEBUG True
CMD ["/wait-for-it.sh", "db:3306", "-t", "0", "--", "perl", "report_aws_spending"]
