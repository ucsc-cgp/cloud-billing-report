# These resources are not deployed; they are only provided for convenience
# to document the resources that Erich has provisioned manually.
# The actual state of these resources may differ.

resource "aws_cur_report_definition" "report" {
  report_name          = "ucsc_billing_report"
  time_unit            = "DAILY"
  format               = "Parquet"
  compression          = "Parquet"
  s3_bucket            = aws_s3_bucket.report
  s3_prefix            = "ucsc_billing_report"
  s3_region            = aws_s3_bucket.report.region
  additional_artifacts = ["ATHENA"]
  report_versioning    = "OVERWRITE_REPORT"
}

resource "aws_s3_bucket" "report" {
  policy = <<POLICY
{
 "Version": "2008-10-17",
 "Statement": [
   {
     "Effect": "Allow",
     "Principal": {
       "Service": "billingreports.amazonaws.com"
     },
     "Action": [
       "s3:GetBucketAcl",
       "s3:GetBucketPolicy"
     ],
     "Resource": "${aws_s3_bucket.report.arn}/*"
   },
   {
     "Effect": "Allow",
     "Principal": {
       "Service": "billingreports.amazonaws.com"
     },
     "Action": [
       "s3:PutObject"
     ],
     "Resource": "${aws_s3_bucket.report.arn}"
   }
 ]
}
POLICY
}

resource "aws_iam_role" "report" {
  name               = "report"
  assume_role_policy = <<POLICY
{
   "Version": "2012-10-17",
   "Statement": [
       {
           "Effect": "Allow",
           "Action": [
               "s3:ListBucket",
               "s3:GetBucketLocation"
           ],
           "Resource": "${aws_s3_bucket.report.arn}"
       },
       {
           "Effect": "Allow",
           "Action": [
               "s3:GetObject"
           ],
           "Resource": "${aws_s3_bucket.report.arn}/*"
       }
   ]
}
POLICY
}