import boto3
import datetime
from dateutil import relativedelta
from pathlib import Path
import os
import json
import gzip
import csv
from src.utils.config import Config

def createAwsBillingManifestObjectPath(s3ObjectPrefix: 'String', dayInMonth: 'datetime.date') -> 'String':
    """
    The AWS billing report is in a bucket named 'edu-ucsc-bd2k-billing' under a path that looks similar to
    'ucsc_billing_report/ucsc_billing_report/12345-67890/ucsc_billing_report-Manifest.json'
    
    :param s3ObjectPrefix: This prefix is used to create the full object path
    :param dayInMonth: The billing CSV is created for an entire month, and the file is named with the start and
        end month in the name. For example, the CSV for January 2022 will have '20220101-20220201' in the file name. This parameter indicates
        which month we are interested in.
    :returns: Returns the calculated path to the object.
    """
    # Create the strings representing the starting and ending month of
    startingMonth = dayInMonth.strftime('%Y%m01')
    endingMonth = (dayInMonth + relativedelta.relativedelta(months=1)).strftime('%Y%m01')
    
    # Create the full path. This was created arbitrarily, which is why there is so much redundancy :(
    manifestPath = Path(s3ObjectPrefix)
    manifestPath /= s3ObjectPrefix
    manifestPath /= f'{startingMonth}-{endingMonth}'
    manifestPath /= f'{s3ObjectPrefix}-Manifest.json'
    
    # Return the path as a String
    print(f"Billing manifest to download: {manifestPath.as_posix()}")
    return manifestPath.as_posix()

def downloadAwsBillingCsv(
    s3Client: 'botocore.client.S3',
    s3BucketName: 'String',
    s3BillingManifestPath: 'String',
    downloadDirectory: 'String',
    manifestPathSuffix: 'String',
    csvPathSuffix: 'String') -> 'String':
    """
    Downloads the billing AWS CSV to the provided directory.
    
    :param s3Client: The S3 client we will use to make AWS API calls
    :param s3BucketName: The name of the S3 bucket we are accessing
    :param s3BillingManifestPath: The String path to the desired manifest in the S3 bucket
    :param downloadDirectory: Where we want to download the manifest to
    :param manifestPathSuffix: The name the manifest file will be saved as
    :param csvPathSuffix: The Name the CSV file will be saved as
    
    :returns: Returns the path to the download file
    """
    
    # Download the manifest file locally, we will use this to determine the path for the actual csv
    manifestPath = os.path.join(downloadDirectory, manifestPathSuffix)
    with open(manifestPath, "wb") as manifestJson:
        s3Client.download_fileobj(s3BucketName, s3BillingManifestPath, manifestJson)
        print(f"Downloaded manifest to: {manifestPath}")
        
    # Find the billing CSV path, take the first csv found in the manifest list
    billingCsvFileName = json.load(open(manifestPath, "r"))["reportKeys"][0]
    print(f"Billing CSV to download: {billingCsvFileName}")
    
    # Download the CSV file
    csvGzipFilePath = os.path.join(downloadDirectory, csvPathSuffix)
    with open(csvGzipFilePath, "wb") as csvFile:
        s3Client.download_fileobj(s3BucketName, billingCsvFileName, csvFile)
        print(f"Downloaded CSV to: {csvGzipFilePath}")
        
    # Return the path to the CSV so we can read it in later
    return csvGzipFilePath

def readInCsv(csvPath: 'String') -> 'DictReader':
    """
    Given the path to a gzipped csv file, read it into a DictReader
    :param csvPath: Path to the desired CSV file
    :returns: A DictReader
    """
    with gzip.open(csvPath, "r") as gzipCsv:
        csvLines = gzipCsv.read().decode().splitlines()
        return csv.DictReader(csvLines)




