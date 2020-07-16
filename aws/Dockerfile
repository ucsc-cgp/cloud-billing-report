FROM perl:5.30.2
RUN mkdir -p /root/aws-reporting/
WORKDIR /root/aws-reporting/
COPY cpanfile /root/aws-reporting/
RUN cpan cpanm
RUN cpanm --installdeps .
RUN ln -s /bin/date /usr/bin/date
COPY report_aws_spending /root/aws-reporting/
COPY config.pl /root/aws-reporting/
CMD ["perl", "report_aws_spending"]
