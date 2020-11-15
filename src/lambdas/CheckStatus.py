import json
import boto3
import requests
import jwt
import datetime
from requests.auth import AuthBase


def lambda_handler(event, context):
    result = event["Payload"]["Input"]
    translation_type = result["translate_type"]
    ordernumber = result["ordernumber"]
    bucket = result["bucket"]
    target_lang = result["target_lang"]
    filename = result["filename"]
    
    if translation_type == "AWS":
        client = boto3.client('translate')
        response = client.describe_text_translation_job(JobId=ordernumber)["TextTranslationJobProperties"]
        JobStatus = "Wait" if response["JobStatus"] == "IN_PROGRESS" or response["JobStatus"] == "SUBMITTED" else response["JobStatus"]
        JobStatus = "Finished"  if JobStatus == "COMPLETED" else JobStatus
        JobStatus = JobStatus if JobStatus == "Wait" or JobStatus == "Finished" else "Error"
        
        if JobStatus == "Finished":
            result["wait"] = 0
            acc_id = aws_account_id = context.invoked_function_arn.split(":")[4]
            output_path = "output_" + filename.split(".")[0] + "/"
            path_to_file = bucket + "/" + output_path + acc_id + "-TranslateText-" + ordernumber + "/"
            boto3.resource("s3").Object(bucket, target_lang + "_" + filename).copy_from(CopySource=path_to_file + target_lang + "." + filename)
            delete_s3_dir(output_path, bucket)
            input_path = "input_" + filename.split(".")[0] + "/"
            delete_s3_dir(input_path, bucket)
            
            
        elif JobStatus == "Wait":
            result["wait"] = 600 #Machines most of the time assigned after 600 seconds
            
        else: #TODO
            pass
        
    elif translation_type == "DeepL":
        auth_key = result["auth_key"]
        doc_key = result["doc_key"]
        data = {
          'auth_key': auth_key,
          'document_key': doc_key
        }
        response = requests.post('https://api.deepl.com/v2/document/' + ordernumber, data=data).json()
        
        JobStatus = "Wait" if response["status"] == "queued" or response["status"] == "translating" else response["status"]
        JobStatus = "Finished"  if JobStatus == "done" else JobStatus
        JobStatus = JobStatus if JobStatus == "Wait" or JobStatus == "Finished" else "Error"
        if JobStatus == "Finished":
            result["wait"] = 0
            data = {
              'auth_key': auth_key,
              'document_key': doc_key
            }
            r = requests.post('https://api.deepl.com/v2/document/' + ordernumber + '/result', data=data)
            boto3.client('s3').put_object(Bucket = bucket, Body = r.content, Key = target_lang + "_" + filename)
        elif JobStatus == "Wait":
            if response["status"] == "translating":
                result["wait"] = response["seconds_remaining"]
            else:
                result["wait"] = 180
        else: #TODO
            pass
            
    elif translation_type == "t24":
        auth_key = result["auth_key"]
        uuid = result["uuid"]
        target_lang = result["target_lang"]
        url= os.environ['t24prefix'] + 'api/order/' + ordernumber + "/status/"
        auth_hook=ApiAuth(customer_uuid=uuid, secret_api_token=auth_key)
        response = requests.get(url, auth=auth_hook).json()
        JobStatus = "Wait" if response == "WORKING" else response
        JobStatus = "Finished"  if JobStatus == "DELIVERED" else JobStatus
        JobStatus = JobStatus if JobStatus == "Wait" or JobStatus == "Finished" else "Error" 
        if JobStatus == "Finished":
            result["wait"] = 0
            url= os.environ['t24prefix'] + 'api/order/' + ordernumber + "/targetDocuments/"
            items = requests.get(url, auth=auth_hook).json()["items"]
            headers = {
              'Accept': '*/*'
            }
            for item in items:
                document_id = item["documentId"]
                filename = target_lang + "_" + item["filename"]
                url= os.environ['t24prefix'] + 'api/order/' + ordernumber + "/targetDocument/" + str(document_id) + "/content"
                r = requests.get(url, auth=auth_hook, headers = headers)
                boto3.client('s3').put_object(Bucket = bucket, Body = r.content, Key = filename)
        elif JobStatus == "Wait":
            result["wait"] = 3600
        else: #TODO
            pass
        
    return result

def delete_s3_dir(path, bucket):
    keys = []
    for item in boto3.client('s3').list_objects(Bucket=bucket, Prefix=path)["Contents"]:
        keys.append({"Key": item["Key"]})
    objects = {"Objects":keys}
    boto3.client('s3').delete_objects(Bucket=bucket, Delete=objects)
    
class ApiAuth(AuthBase):
    def __init__(self, customer_uuid, secret_api_token):
        self.customer_uuid = customer_uuid
        self.secret_api_token = secret_api_token

    def encode_auth_token(self):
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=0, seconds=1000),
            'iat': datetime.datetime.utcnow(),
            'sub': self.customer_uuid
        }
        return jwt.encode(
            payload,
            self.secret_api_token,
            algorithm='HS256'
        )


    def __call__(self, r):
        r.headers['Authorization'] = 'Bearer ' + self.encode_auth_token().decode("utf-8")
        return r