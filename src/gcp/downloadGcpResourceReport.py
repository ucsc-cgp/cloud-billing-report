from google.cloud import bigquery

def downloadGcpBillingRows(bigQueryTable: 'string', day: 'datetime.date'):

    # Create the bigquery client
    client = bigquery.Client()

    # get the proper day and month formatting
    queryMonth = day.strftime('%Y%m')
    queryDay = day.strftime('%Y-%m-%d')

    # noinspection SqlNoDataSourceInspection
    query = f'''SELECT
          project.name,
          service.description,
          SUM(CASE WHEN DATE(usage_start_time) <= '{queryDay}' THEN cost + IFNULL(creds.amount, 0) ELSE 0 END) AS cost_month,
          SUM(CASE WHEN DATE(usage_start_time)  = '{queryDay}' THEN cost + IFNULL(creds.amount, 0) ELSE 0 END) AS cost_today
        FROM `{bigQueryTable}`
        LEFT JOIN UNNEST(credits) AS creds
        WHERE invoice.month = '{queryMonth}'
        GROUP BY project.name, service.description
        ORDER BY LOWER(project.name) ASC, service.description ASC'''
    queryJob = client.query(query)
    resourceRows = list(queryJob.result())

    return resourceRows
