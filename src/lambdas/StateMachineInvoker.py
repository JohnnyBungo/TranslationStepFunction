import boto3
import os
import json

def lambda_handler(event, context):
    if event["Records"][0]["eventName"] == "INSERT":
        Inputvars = event["Records"][0]["dynamodb"]["NewImage"]
        result = {"bucket": Inputvars["bucket"]["S"], "translate_type": Inputvars["translate_type"]["S"], "source_lang": Inputvars["source_lang"]["S"], "target_lang": Inputvars["target_lang"]["S"], "filename": Inputvars["filename"]["S"]}
        if "auth_key" in Inputvars:
            result["auth_key"] = Inputvars["auth_key"]["S"]
        if "uuid" in Inputvars: #TODO Errorhandling for missing Value
            result["uuid"] = Inputvars["uuid"]["S"]
            result["specialisation_code"] = Inputvars["specialisation_code"]["S"]
            result["product_name"] = Inputvars["product_name"]["S"]
            result["desired_delivery_time"] = Inputvars["desired_delivery_time"]["S"]
            new_list = []
            for map in Inputvars["special_fields"]["L"]:
                new_map = {}
                for key_type in map["M"]["Key"]:
                    new_map["key"] = map["M"]["Key"][key_type]
                for value_type in map["M"]["Value"]:
                    new_map["value"] = map["M"]["Value"][value_type]
                new_list.append(new_map)
            result["special_fields"] = new_list
        client = boto3.client('stepfunctions')
        response = client.start_execution(
            stateMachineArn = os.environ['StepARN'],
            input = json.dumps(result))