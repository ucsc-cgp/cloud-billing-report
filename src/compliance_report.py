from src.report_resource import report_resource


class compliance_report():
    def __init__(self):
        return

    # It's really silly that I have to do this. The boto3 call should return the resource type
    # in the response dict, especially because I provide a list of resource types in the first place
    def get_resource_type(self, resource_arn):
        if ":instance/" in resource_arn:
            return "ec2:instance"
        elif ":volume/" in resource_arn:
            return "ec2:volume"
        elif ":snapshot/" in resource_arn:
            return "ec2:snapshot"
        elif "s3" in resource_arn:
            return "s3:bucket"

        return ""

    def get_resource_by_tags(self, boto3_sts_service_object, account_id, account_name, region):

        # Create a new boto3 session for retrieving resource tags
        resource_tag_session = boto3_sts_service_object.get_boto3_session(region, 'resourcegroupstaggingapi')
        paginator = resource_tag_session.get_paginator("get_resources")

        # These are the types of resources we are querying for
        resource_type_filters = ["s3", "ec2:instance", "ec2:volume", "ec2:snapshot"]

        # Get the list of response dictionaries for each resource of the desired type
        resource_response_dict = paginator.paginate(ResourceTypeFilters=resource_type_filters)

        resource_object_list = []
        for page in resource_response_dict:  # for every page
            for resource_dict in page["ResourceTagMappingList"]:  # for every resource on that page
                resource_arn = resource_dict["ResourceARN"]  # get the ARN associated with the resource
                resource = report_resource(resource_arn,
                                           self.get_resource_type(resource_arn),
                                           account_id,
                                           account_name,
                                           region)

                # add tags to the resource
                for tag in resource_dict["Tags"]:
                    if tag["Key"] == "Owner" or tag["Key"] == "owner" or tag["Key"] == "noncompliant-maid-service":
                        resource.add_tag_value(tag["Key"], tag["Value"])
                resource.set_compliance_status()

                # append the resource to our object list
                resource_object_list.append(resource)

        return resource_object_list

    def generate_full_compliance_report(self, boto3_sts_service_object, account_id_list, account_name_list, arn_list, region_list):
        # There should be a 1:1 ratio of ARNs to accounts
        assert len(account_id_list) == len(account_name_list)
        assert len(account_name_list) == len(arn_list)
        n = len(account_id_list)

        full_resource_list = []

        # for every account
        for i in range(n):

            # get the account name and role arn
            account_id = account_id_list[i]
            account_name = account_name_list[i]
            arn = arn_list[i]

            # assume the IAM role associated with this account
            boto3_sts_service_object.assume_new_role(arn)

            # for every region we want to query, get all
            for region in region_list:
                full_resource_list += self.get_resource_by_tags(boto3_sts_service_object, account_id, account_name, region)

        return full_resource_list
