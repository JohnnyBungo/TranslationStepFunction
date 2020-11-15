import json
import jwt
import requests
import datetime
from requests.auth import AuthBase        

def lambda_handler(event, context):
    result = event["Payload"]["Input"]

    auth_key = result["auth_key"]
    ordernumber = result["ordernumber"]
    uuid = result["uuid"]
    url= os.environ['t24prefix'] + 'api/order/' + ordernumber + "/status/"
    auth_hook=ApiAuth(customer_uuid=uuid, secret_api_token=auth_key)
    r = requests.get(url, auth=auth_hook).json()
    if r == "VALID":
        result["wait"] = 0
        #TODO Quota
        url= os.environ['t24prefix'] + 'api/order/' + ordernumber + "/place"
        r = requests.put(url, auth=auth_hook)
        
    elif r == "INVALID":
        #TODO Error Handling
        pass
    else:
        result["wait"] = 60
        
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