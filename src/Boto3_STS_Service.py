import boto3
import os


class Boto3_STS_Service(object):
    def __init__(self):
        self.session = boto3.session.Session(
            profile_name=os.environ["AWS_PROFILE"]
        )
        self.sts_connection = self.session.client("sts")

        self.assume_role_object = None
        self.assume_role_credentials = None
        self.assume_role_client = None

    def assume_new_role(self, role_arn: str, role_session_name="billing_report", duration=900):
        # Assume the desired role
        self.assume_role_object = self.sts_connection.assume_role(
            RoleArn=role_arn,
            RoleSessionName=role_session_name,
            DurationSeconds=duration
        )

        # Get credentials for the assumed role
        self.assume_role_credentials = self.assume_role_object['Credentials']

    def get_boto3_session(self, region):
        # Ensure we have assumed a role (this doesn't check that the session hasn't timed out)
        assert self.assume_role_object is not None
        tmp_credentials = self.assume_role_credentials

        # Isolate the credentials we need to start a new session
        tmp_access_key = tmp_credentials["AccessKeyId"]
        tmp_secret_key = tmp_credentials["SecretAccessKey"]
        security_token = tmp_credentials["SessionToken"]

        # Start a config client
        self.assume_role_client = boto3.client('config',
                                         aws_access_key_id=tmp_access_key,
                                         aws_secret_access_key=tmp_secret_key,
                                         aws_session_token=security_token,
                                         region_name=region)

        return self.assume_role_client
