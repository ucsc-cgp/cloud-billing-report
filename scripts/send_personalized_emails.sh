#!/bin/bash
for filename in /tmp/personalizedEmails/*.eml; do
    # send the email file
    #/usr/sbin/sendmail -t < $filename
    echo $filename
    # remove the file
    # rm $filename
done