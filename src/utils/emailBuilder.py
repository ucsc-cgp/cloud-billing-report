import jinja2
import datetime
from email.message import EmailMessage
from src.utils.config import Config

class EmailBuilder:
    
    def __init__(self, jinjaTemplates="src/templates/"):
        self.jinjaEnv = jinja2.Environment(loader=jinja2.FileSystemLoader(jinjaTemplates))
        self.jinjaEnv.filters.update({
            'ymd': lambda d: d.strftime('%Y/%m/%d'),
            'ym': lambda d: d.strftime('%Y/%m')
        })
        
    def renderAwsEmail(self,
                 reportDate: datetime.date,
                 emailFrom: 'String',
                 recipients: 'List[String]',
                 individual=False,
                 **templateVars) -> str:
        
        # Configure the email
        msg = EmailMessage()
        msg['Subject'] = f'AWS Report for {reportDate}'
        msg['From'] = emailFrom
        msg['To'] = recipients
        
        # Create the HTML content using Jinja. If this email is for an individual user, choose a specific template
        tmpl = self.jinjaEnv.get_template(Config.AWS_INDIVIDUAL_REPORT_TEMPLATE if individual else Config.AWS_REPORT_TEMPLATE)
        body = tmpl.render(reportDate=reportDate, **templateVars)
        
        # Set the email content to the Jinja template
        msg.set_content(body, subtype='html')
        
        # Return the email as a String
        return msg.as_string()
    
    def renderGcpEmail(self,
                 reportDate: datetime.date,
                 emailFrom: 'String',
                 recipients: 'List[String]',
                 **templateVars):
        
        # Configure the email
        msg = EmailMessage()
        msg['Subject'] = f'GCP Report for {reportDate}'
        msg['From'] = emailFrom
        msg['To'] = recipients
        
        tmpl = self.jinjaEnv.get_template(Config.GCP_REPORT_TEMPLATE)
        body = tmpl.render(reportDate=reportDate, **templateVars)
        
        # Set the email content to the Jinja template
        msg.set_content(body, subtype='html')
        
        # Return the email as a String
        return msg.as_string()