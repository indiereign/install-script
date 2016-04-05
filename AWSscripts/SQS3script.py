# Instructions
# python SQS3script.py --s3bucket <bucket name>  --region <region> --acnumber <account number>  ( --sqsurl <sqs-url>  or --sqsname <sqs queue name> ) --user <user name>

# Provide the SQS queue url in case queue already exists otherwise provide a name for the SQS queue to be created
# This script assumes that the aws credentials are stored at ~/.aws/credentials
# region examples: us-east-1, us-west-2 etc.


import boto
import boto3
import boto.sqs
import boto.sqs.connection
import json
import os
import re
import sys

from boto.sqs.connection import SQSConnection
from boto.sqs.message import Message

from optparse import OptionParser


parser = OptionParser()
parser.add_option("--acnumber", dest="acnumber",
                  help="account number")
parser.add_option("--s3bucket", dest="s3bucket",
                  help="s3 bucket name")
parser.add_option("--sqsurl", dest="sqsurl",
                  help="sqsurl")
parser.add_option("--region", dest="region",
                  help="region")
parser.add_option("--user", dest="user",
                  help="user")
parser.add_option("--sqsname", dest="sqsname",
                  help="sqsname")
parser.add_option("--flag", dest="flag",
                  help="flag")
parser.add_option("--setups3", dest="setups3", 
                  help="setups3")

(opts, args) = parser.parse_args()


s3bucket = opts.s3bucket
acnumber = opts.acnumber
sqsurl = opts.sqsurl
region = opts.region
sqsname = opts.sqsname
user = opts.user
flag = opts.flag
setups3 = opts.setups3


if not s3bucket:
    parser.error("S3 bucket name not provided")

if not acnumber:
    parser.error("Account number not provided")

if not region:
    parser.error("SQS queue/Bucket region not provided")



if (sqsname == None or sqsname == '') and (sqsurl == None or sqsurl == ''):
  print "Please provide the SQS name or the SQS url" 
  sys.exit()


if (sqsname != None and sqsname != '') and (sqsurl != None and sqsurl != ''):
  print "Please provide either the SQS name or the SQS url. SQS name to create a new queue; SQS url to use an existing queue" 
  sys.exit()


with open(os.environ['HOME'] + '/.aws/credentials') as f:
    for line in f:
        if "aws_access_key_id" in line:
             access_key = line.split("=",1)[1].strip()
        if "aws_secret_access_key" in line:
             secret_key = line.split("=",1)[1].strip()


conn = boto.sqs.connect_to_region(region, aws_access_key_id=access_key,  aws_secret_access_key=secret_key)


if sqsurl != None and sqsurl != '':
    queue_name = sqsurl.rsplit('/', 1)[1]
    
    my_queue = conn.get_queue(queue_name)

    # get queue's policy

    queue_attr_raw = conn.get_queue_attributes(my_queue, attribute='All')

    queue_attr = str(queue_attr_raw) 

    if 'arn:aws:s3' in queue_attr:
        # append a bucket to the existing policy
       
        start = '\"aws:SourceArn\":'
        end = '}}}'
        result = re.search('%s(.*)%s' % (start, end), queue_attr).group(1)
        
        
        leftbracketremoved = result.replace('[','')
        rightbracketremoved = leftbracketremoved.replace(']','')

        addon  = '[' + rightbracketremoved + ',' + '\"arn:aws:s3:*:*:' + s3bucket +'\"' +']'
        

        text = """ {
          "Version": "2008-10-17",
          "Id": "PolicyExample",
          "Statement": [
            {
              "Sid": "example-statement-ID",
              "Effect": "Allow",
              "Principal": {
                "AWS": "*"
              },
              "Action": "SQS:SendMessage",
              "Resource": "arn:aws:sqs:%s:%s:%s",
              "Condition": {
                "ArnLike": {
                  "aws:SourceArn": %s   
                }
              }
            },
            {
              "Sid": "GiveAccessToLoggly",
              "Effect": "Allow",
              "Principal": {
                "AWS": "arn:aws:iam::%s:root"
              },
              "Action": "SQS:*",
              "Resource": "arn:aws:sqs:%s:%s:%s"
            }
          ]
        }
        """ % (region, acnumber, queue_name, addon, acnumber, region, acnumber, queue_name)

        
        parsed = json.loads(text)
       
        conn.set_queue_attribute(my_queue, 'Policy', json.dumps(parsed))

    else:
        conn.set_queue_attribute(my_queue, 'Policy', json.dumps({
          "Version": "2008-10-17",
          "Id": "PolicyExample",
          "Statement": [
            {
              "Sid": "example-statement-ID",
              "Effect": "Allow",
              "Principal": {
                "AWS": "*"
              },
              "Action": "SQS:SendMessage",
              "Resource": "arn:aws:sqs:" + region + ":" + acnumber + ":" + queue_name,
              "Condition": {
                "ArnLike": {
                  "aws:SourceArn": "arn:aws:s3:*:*:" + s3bucket
                }
              }
            },
            {
              "Sid": "GiveAccessToLoggly",
              "Effect": "Allow",
              "Principal": {
                "AWS": "arn:aws:iam::" + acnumber + ":root"
              },
              "Action": "SQS:*",
              "Resource": "arn:aws:sqs:" + region + ":" + acnumber + ":" + queue_name
            }
          ]
        }))

    # s3 bucket notification configuration 
    client = boto3.client('s3', region)

  
    response = client.put_bucket_notification_configuration(
        Bucket=s3bucket,
        NotificationConfiguration={ 
            "QueueConfigurations": [{
             "Id": "Notification",
             "Events": ["s3:ObjectCreated:*"],
             "QueueArn": "arn:aws:sqs:" + region + ":" + acnumber + ":" + queue_name
        }],
        }
    )




if sqsname != None and sqsname != '':

    sqs = boto.connect_sqs(access_key, secret_key)

    # creates a new queue
    q = sqs.create_queue(sqsname)

    my_queue = conn.get_queue(sqsname)

    # attach a policy to this queue

    conn.set_queue_attribute(my_queue, 'Policy', json.dumps({
          "Version": "2008-10-17",
          "Id": "PolicyExample",
          "Statement": [
            {
              "Sid": "example-statement-ID",
              "Effect": "Allow",
              "Principal": {
                "AWS": "*"
              },
              "Action": "SQS:SendMessage",
              "Resource": "arn:aws:sqs:" + region + ":" + acnumber + ":" + sqsname,
              "Condition": {
                "ArnLike": {
                  "aws:SourceArn": "arn:aws:s3:*:*:" + s3bucket
                }
              }
            },
            {
              "Sid": "GiveAccessToLoggly",
              "Effect": "Allow",
              "Principal": {
                "AWS": "arn:aws:iam::" + acnumber + ":root"
              },
              "Action": "SQS:*",
              "Resource": "arn:aws:sqs:" + region + ":" + acnumber + ":" + sqsname
            }
          ]
        }))

    # s3 bucket notification configuration 
    client = boto3.client('s3', region)

    response = client.put_bucket_notification_configuration(
        Bucket=s3bucket,
        NotificationConfiguration={ 
            "QueueConfigurations": [{
             "Id": "Notification",
             "Events": ["s3:ObjectCreated:*"],
             "QueueArn": "arn:aws:sqs:" + region + ":" + acnumber + ":" + sqsname
        }],
        }
    )



if user != None and user != '':

    iam = boto.connect_iam(access_key, secret_key)
 
    # create an IAM user
    response = iam.create_user(user)


    # create an access key
    iam.create_access_key(user)
    response = iam.create_access_key(user)
    loggly_access_key = response.access_key_id
    loggly_secret_key = response.secret_access_key

    print "Access key for Loggly"

    print loggly_access_key

    print "Secret key for Loggly"

    print loggly_secret_key


    policy_json = """{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "Sidtest",
            "Effect": "Allow",
            "Action": [
                "sqs:*"
            ],
            "Resource": [
                "arn:aws:sqs:%s:%s:%s"
            ]
        }
    ]
    }""" % (region, acnumber, sqsname,)


    response = iam.put_user_policy(user,
                                   'TestPolicy',
                                   policy_json)
