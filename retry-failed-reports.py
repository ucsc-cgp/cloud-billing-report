"""
Retries failed reports given a list of failed report types and dates.
"""
import argparse
import datetime
import subprocess


def aws_report(date: str) -> bytes:
    report = subprocess.run(['docker', 'run',
                             '-v', '/root/reporting/config.json:/config.json:ro',
                             'ghcr.io/ucsc-cgp/report:latest',
                             'aws', date],
                            check=True,
                            capture_output=True,
                            shell=False)
    return report.stdout


def gcp_report(date: str) -> bytes:
    report = subprocess.run(['docker', 'run',
                             '-v', '/root/reporting/config.json:/config.json:ro',
                             'ghcr.io/ucsc-cgp/report:latest',
                             'gcp', date],
                            check=True,
                            capture_output=True,
                            shell=False)
    return report.stdout


reports = {
    'aws': aws_report,
    'gcp': gcp_report
}


def main(path: str):
    try:
        with open(path, 'r') as fail_file:
            failures = fail_file.read().splitlines()
    except FileNotFoundError:
        failures = []

    still_failing = []
    for failure in set(failures):
        report_type, report_date = failure.split(',')
        assert report_type in reports
        assert datetime.datetime.strptime(report_date, '%Y-%m-%d')
        try:
            report = reports[report_type](report_date)
        except subprocess.CalledProcessError:
            still_failing.append(failure)
        else:
            subprocess.run(['/usr/sbin/sendmail', '-t'],
                           check=True,
                           shell=False,
                           input=report)

    with open(path, 'w') as fail_file:
        fail_file.write('\n'.join(set(still_failing)))


if __name__ == '__main__':
    # https://youtrack.jetbrains.com/issue/PY-41806
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('fail_file_path',
                        help='Path to a file listing report failures in form '
                             '`report_type,YYYY-MM-DD`, one per line.')
    arguments = parser.parse_args()
    main(arguments.fail_file_path)
