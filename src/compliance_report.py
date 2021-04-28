from src.report_resource import report_resource


class compliance_report():
    def __init__(self):
        return

    def generate_compliance_list(self, aws_config_client, aws_config_rule, aws_account_id, aws_account_name, aws_region, compliance_status='NON_COMPLIANT'):
        # query AWS Config to get information about resources that are NON_COMPLIANT with a specific config rule
        non_compliant_details = aws_config_client.get_compliance_details_by_config_rule(
            ConfigRuleName=aws_config_rule,
            ComplianceTypes=[compliance_status]
        )

        non_compliant_resources = []
        next_page = True
        while next_page:

            # Add the ResourceId of all NON_COMPLIANT resources to a list
            if len(non_compliant_details["EvaluationResults"]) > 0:
                for result in non_compliant_details['EvaluationResults']:
                    resource = report_resource(result['EvaluationResultIdentifier']['EvaluationResultQualifier']['ResourceId'],
                                               result['EvaluationResultIdentifier']['EvaluationResultQualifier']['ResourceType'],
                                               aws_account_id,
                                               aws_account_name,
                                               aws_region,
                                               compliance_status)
                    non_compliant_resources.append(resource)

            # if the response contained a NextToken, we need to continue scanning
            if "NextToken" in non_compliant_details:
                non_compliant_details = aws_config_client.get_compliance_details_by_config_rule(
                    ConfigRuleName=aws_config_rule,
                    ComplianceTypes=[compliance_status],
                    NextToken=non_compliant_details["NextToken"]
                )
            else:
                next_page = False

        return non_compliant_resources

    def get_resource_tags(self, boto3_sts_service_object, account_region_list, region):

        # List of the arns of all the objects we want to query
        resource_arn_list = []

        # for every resource, add it's arn to the resource_arn_list
        for resource in account_region_list:
            resource_arn_list.append(f"arn:aws:s3:::{resource.get_resource_id()}")

        # Create a new boto3 session for retrieving resource tags
        resource_tag_session = boto3_sts_service_object.get_boto3_session(region, 'resourcegroupstaggingapi')
        paginator = resource_tag_session.get_paginator("get_resources")

        # Get the list of response dictionaries for each resource in the resource_arn_list
        resource_response_dict = paginator.paginate(ResourceARNList=resource_arn_list)

        # TODO: This is pretty ugly, should be fixed up, what this does is:
        # 1. For every page in our pagination
        # 2. For every resource reported on each page
        # 3. Match the resource returned with a report_resource object in account_region_list
        # 4. Look through all the tags of the resource and update the report_resource object with the email tagging info.
        for page in resource_response_dict:  # for every page
            for resource_dict in page["ResourceTagMappingList"]:  # for every resource on that page
                resource_arn = resource_dict["ResourceARN"]  # get the ARN associated with the resource
                for resource in account_region_list:  # look through all our resources and match by ARN
                    if f"arn:aws:s3:::{resource.get_resource_id()}" == resource_arn:
                        for tag in resource_dict["Tags"]:
                            if "Owner" == tag["Key"] or "owner" == tag["Key"]:
                                resource.add_owner_tag_value(tag["Key"], tag["Value"])

    def generate_full_compliance_report(self, boto3_sts_service_object, account_id_list, account_name_list, arn_list, region_list,
                                        aws_config_rule_name, compliance_status='NON_COMPLIANT'):
        # There should be 1 arn per account
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

            # for every region we want to query
            for r in region_list:
                boto3_sts_service_object.assume_new_role(arn)
                tmp_session = boto3_sts_service_object.get_boto3_session(r, 'config')
                account_region_list = self.generate_compliance_list(tmp_session, aws_config_rule_name, account_id, account_name, r,
                                                                    compliance_status)

                # If we queried for compliant resources, we need to query again for resource tags.
                if compliance_status == 'COMPLIANT' and len(account_region_list) > 0:
                    self.get_resource_tags(boto3_sts_service_object, account_region_list, r)

                # add the list of NON_COMPLIANT resources
                full_resource_list += account_region_list


        return full_resource_list
