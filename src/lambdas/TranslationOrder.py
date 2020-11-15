import json
import boto3
import os
import datetime
import jwt
import hashlib
from smart_open import smart_open
import requests
from requests.auth import AuthBase
    



def lambda_handler(event, context):
    result = event["Payload"]["Input"]
    translate_type = result["translate_type"]
    bucket = result["bucket"]
    source_lang = result["source_lang"]
    target_lang = result["target_lang"]
    filename = result["filename"]
    
    if translate_type == "AWS":
        
        input_path = "s3://" + bucket + "/input_" + filename.split(".")[0] + "/"
        output_path = "s3://" + bucket + "/output_" + filename.split(".")[0] + "/"
        boto3.resource("s3").Object(bucket, "input_" + filename.split(".")[0] + "/" + filename).copy_from(CopySource=bucket + "/" + filename)
        boto3.client('s3').put_object(Bucket=bucket, Key=("output_" + filename.split(".")[0] + "/"))
        client = boto3.client('translate')
        response = client.start_text_translation_job(
        InputDataConfig={
            'S3Uri': input_path,
            'ContentType': switcher(filename.split(".")[-1]) #TODO Error for invalid doctype
        },
        OutputDataConfig={
            'S3Uri': output_path
        },
        DataAccessRoleArn=os.environ['TranslateRoleName'],
        SourceLanguageCode=source_lang,
        TargetLanguageCodes=[
            target_lang
        ],
        TerminologyNames=[
            source_lang + "_" + target_lang,
        ]
    )
        result["ordernumber"] = response["JobId"]
        
    elif translate_type == "DeepL":
        client = boto3.client('s3')
        url = "https://api.deepl.com/v2/document"
        auth_key = result["auth_key"]
        files = {
            'file': (filename, smart_open('s3://' + bucket + '/' + filename, 'rb')), 
            'auth_key': (None, auth_key),
            'target_lang': (None, target_lang),
        }
        response = requests.post(url, files=files).json()
        result["ordernumber"] = response["document_id"]
        result["doc_key"] = response["document_key"]

    elif translate_type == "t24":
        client = boto3.client('s3')
        
        ########################Order request#########################
        uuid = result["uuid"]
        auth_key = result["auth_key"]
        auth_hook=ApiAuth(customer_uuid=uuid, secret_api_token=auth_key)
        url= os.environ['t24prefix'] + "api/order"
        specialisation_code = result["specialisation_code"]
        product_name = result["product_name"]
        desired_delivery_time = result["desired_delivery_time"]
        target_lang = bcp47(target_lang) #TODO Error Handling
        source_lang = bcp47(source_lang) #TODO Error Handling
        special_fields = result["special_fields"]
        order_info={
            "sourceLanguage": source_lang,
            "targetLanguage": target_lang,
            "productName": product_name,
            "specialisationCode": specialisation_code,
            "desiredDeliveryTime": desired_delivery_time,
            "specialFields": special_fields
        }
        
        r = requests.post(url, json = order_info, auth=auth_hook)
        ordernumber = r.json()['orderNumber'] #TODO Error handling
        result["ordernumber"] = ordernumber
        
        ########################Document Upload#########################
        headers = {
          'Accept': 'application/json'
        }
        
        file = smart_open('s3://' + bucket + '/' + filename, 'rb')
        
        hash_md5 = hashlib.md5()
        for chunk in iter(lambda: file.read(4096), b""):
            hash_md5.update(chunk)
            
        file = smart_open('s3://' + bucket + '/' + filename, 'rb')
        
        r = requests.post(os.environ['t24prefix'] + 'api/order/' + ordernumber + '/sourceDocument', auth = auth_hook,  headers = headers, data={'md5Checksum':hash_md5.hexdigest()}, files={'file':  file})
    return result
    
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


def switcher(doc):
    switcher = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
    return switcher.get(doc, "Invalid doctype")

def bcp47(lang):
    switcher = {
        "de": "de-CH",
        "fr": "fr-CH",
        "en": "en-GB"
    }
    return switcher.get(lang, "Invalid languag")