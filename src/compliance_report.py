class compliance_report():
    def __init__(self):
        return

    def generate_compliance_list(self, aws_config_client, aws_config_rule, compliance_status='NON_COMPLIANT'):
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
                non_compliant_resources += [result['EvaluationResultIdentifier']['EvaluationResultQualifier']['ResourceId'] \
                                           for result in non_compliant_details['EvaluationResults']]

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

    def generate_full_compliance_report(self, boto3_sts_service_object, account_list, arn_list, region_list, aws_config_rule_name, compliance_status='NON_COMPLIANT'):
        # There should be 1 arn per account
        assert len(account_list) == len(arn_list)
        n = len(account_list)

        report_dict = {a: [] for a in account_list}

        # for every account
        for i in range(n):

            # get the account name and arn
            account = account_list[i]
            arn = arn_list[i]

            # for every region we want to query
            for r in region_list:
                boto3_sts_service_object.assume_new_role(arn)
                tmp_session = boto3_sts_service_object.get_boto3_session(r)
                account_region_list = self.generate_compliance_list(tmp_session, aws_config_rule_name, compliance_status)

                # add the list of NON_COMPLIANT resources
                report_dict[account] += account_region_list

        return report_dict
