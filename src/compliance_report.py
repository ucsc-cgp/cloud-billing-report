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

                    # If the resources we are querying are COMPLIANT, we need to know why they are compliant
                    # (i.e. we want to know the value of their "Owner" and "owner" tags)
                    if compliance_status == "COMPLIANT":
                        resource_tags = aws_config_client.list_tags_for_resource(
                            ResourceArn=f"{resource.get_resource_type()}:::{resource.get_resource_id()}", # TODO make this viable for non-S3 resources
                            Limit=50
                        )
                        for tag_dict in resource_tags:
                            if "Owner" == tag_dict["Key"] or "owner" == tag_dict["key"]:
                                resource.add_owner_tag_value(tag_dict["Key"], tag_dict["Value"])

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

    def generate_full_compliance_report(self, boto3_sts_service_object, account_id_list, account_name_list, arn_list, region_list, aws_config_rule_name,
                                        compliance_status='NON_COMPLIANT'):
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
                tmp_session = boto3_sts_service_object.get_boto3_session(r)
                account_region_list = self.generate_compliance_list(tmp_session, aws_config_rule_name, account_id, account_name, r, compliance_status)

                # add the list of NON_COMPLIANT resources
                full_resource_list += account_region_list

        return full_resource_list
