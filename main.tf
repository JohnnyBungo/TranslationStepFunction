################################################-S3-##############################################################

module "s3_input" {
  source = "terraform-aws-modules/s3-bucket/aws"

  bucket = var.input_bucket
  acl    = "private"

}

################################################-DynamoDB-##############################################################

module "dynamodb_table" {
  source = "terraform-aws-modules/dynamodb-table/aws"

  name     = "translation_order"
  hash_key = "id"
  stream_view_type = "NEW_IMAGE"
  stream_enabled = true

  attributes = [
    {
      name = "id"
      type = "N"
    }
  ]
}

#data "aws_dynamodb_table" "translation_order_on_aws" {
#  name = "translation_order"
#  depends_on = [module.dynamodb_table]
#}


################################################-Lambda-##############################################################

module "lambda_StateMachineInvoker" {
  depends_on    = [aws_sfn_state_machine.TranslationStateMachine]
  source        = "terraform-aws-modules/lambda/aws"
  create_role   = true
  function_name = "StateMachineInvoker"
  description   = "Forwards Events in Dynamo to Steps-Function"
  handler       = "StateMachineInvoker.lambda_handler"
  runtime       = "python3.8"
  role_name     = "StateMachineInvoker"
  timeout       = 60
  publish       = true

  source_path = "src/lambdas/StateMachineInvoker.py"

  environment_variables = {
    StepARN = aws_sfn_state_machine.TranslationStateMachine.arn
  }

}

module "lambda_TranslationOrder" {
  depends_on    = [aws_iam_role.TranslationOrder_role]
  source        = "terraform-aws-modules/lambda/aws"
  create_role   = false
  function_name = "TranslationOrder"
  description   = "Sets order for translation. First step in Step-Function"
  handler       = "TranslationOrder.lambda_handler"
  runtime       = "python3.8"
  lambda_role   = aws_iam_role.TranslationOrder_role.arn
  timeout       = 60
  publish       = true

  source_path = "src/lambdas/TranslationOrder.py"

  layers = [
    module.lambda_layer_requests.this_lambda_layer_arn,
    module.lambda_layer_jwt.this_lambda_layer_arn,
    module.lambda_layer_smart_open.this_lambda_layer_arn
  ]

  environment_variables = {
    TranslateRoleName = aws_iam_role.TranslationOrder_role.arn,
    t24api            = var.t24prefix
  }

}

module "lambda_OrderState" {
  source        = "terraform-aws-modules/lambda/aws"
  create_role   = true
  function_name = "CheckOrder"
  description   = "Second step from t24, checks if order is good"
  handler       = "CheckOrder.lambda_handler"
  runtime       = "python3.8"
  role_name     = "CheckOrder"
  timeout       = 60
  publish       = true

  source_path = "src/lambdas/CheckOrder.py"

  layers = [
    module.lambda_layer_requests.this_lambda_layer_arn,
    module.lambda_layer_jwt.this_lambda_layer_arn
  ]

  environment_variables = {
    t24api = var.t24prefix
  }
}

module "lambda_StatusState" {
  source        = "terraform-aws-modules/lambda/aws"
  create_role   = true
  function_name = "CheckStatus"
  description   = "Check if order is finished. Download translated file."
  handler       = "CheckStatus.lambda_handler"
  runtime       = "python3.8"
  role_name     = "CheckStatus"
  timeout       = 60
  publish       = true

  source_path = "src/lambdas/CheckStatus.py"

  layers = [
    module.lambda_layer_requests.this_lambda_layer_arn,
    module.lambda_layer_jwt.this_lambda_layer_arn
  ]

  environment_variables = {
    t24api = var.t24prefix
  }

}

module "lambda_Notification" {
  source        = "terraform-aws-modules/lambda/aws"
  create_role   = true
  function_name = "Notification"
  description   = "Check if order is finished. Download translated file."
  handler       = "Notification.lambda_handler"
  runtime       = "python3.8"
  role_name     = "Notification"
  timeout       = 60
  publish       = true

  source_path = "src/lambdas/Notification.py"

}

################################################-Lambda-Layers-##############################################################

module "lambda_layer_jwt" {
  source = "terraform-aws-modules/lambda/aws"

  create_layer = true

  layer_name          = "jwt-lib"
  description         = "JWT lambda layer (deployed from local)"
  compatible_runtimes = ["python3.8", "python3.7", "python3.6"]

  source_path = "src/layers/jwt"

  store_on_s3 = false
}

module "lambda_layer_requests" {
  source = "terraform-aws-modules/lambda/aws"

  create_layer = true

  layer_name          = "requests-lib"
  description         = "Requests lambda layer (deployed from local)"
  compatible_runtimes = ["python3.8", "python3.7", "python3.6"]

  source_path = "src/layers/requests"

  store_on_s3 = false
}

module "lambda_layer_smart_open" {
  source = "terraform-aws-modules/lambda/aws"

  create_layer = true

  layer_name          = "smart_open-lib"
  description         = "smart_open lambda layer (deployed from local)"
  compatible_runtimes = ["python3.8", "python3.7", "python3.6"]

  source_path = "src/layers/smart_open"

  store_on_s3 = false
}

################################################-Lambda-Permissions-##############################################################

resource "aws_iam_role_policy_attachment" "StateMachineInvoker_dynamo_policy" {
  role       = module.lambda_StateMachineInvoker.lambda_role_name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

resource "aws_iam_role_policy_attachment" "StateMachineInvoker_stepfunction_policy" {
  role       = module.lambda_StateMachineInvoker.lambda_role_name
  policy_arn = "arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess"
}

resource "aws_iam_role_policy_attachment" "StatusState_translate_policy" {
  role       = module.lambda_StatusState.lambda_role_name
  policy_arn = "arn:aws:iam::aws:policy/TranslateFullAccess"
}

resource "aws_iam_role_policy_attachment" "StatusState_s3_policy" {
  role       = module.lambda_StatusState.lambda_role_name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role" "TranslationOrder_role" {
  name               = "TranslationOrder"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "translate.amazonaws.com",
          "lambda.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "TranslationOrder_translate_policy" {
  depends_on = [aws_iam_role.TranslationOrder_role]
  role       = aws_iam_role.TranslationOrder_role.name
  policy_arn = "arn:aws:iam::aws:policy/TranslateFullAccess"
}

resource "aws_iam_role_policy_attachment" "TranslationOrder_iam_policy" {
  depends_on = [aws_iam_role.TranslationOrder_role]
  role       = aws_iam_role.TranslationOrder_role.name
  policy_arn = "arn:aws:iam::aws:policy/IAMFullAccess"
}

resource "aws_iam_role_policy_attachment" "TranslationOrder_s3_policy" {
  depends_on = [aws_iam_role.TranslationOrder_role]
  role       = aws_iam_role.TranslationOrder_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

################################################-Lambda Triggers-##############################################################

#resource "aws_lambda_event_source_mapping" "dynamodb-stream" {

 # event_source_arn                   = data.aws_dynamodb_table.translation_order_on_aws.stream_arn
 # function_name                      = module.lambda_StateMachineInvoker.this_lambda_function_arn
 # batch_size                         = 1
 # maximum_batching_window_in_seconds = 1
 # maximum_record_age_in_seconds      = 600
 # maximum_retry_attempts             = 2
#}


################################################-Step Function-##############################################################

resource "aws_iam_role" "TranslationStateMachine_role" {
  name               = "TranslationStateMachine"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "states.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "TranslationStateMachine_lambda_policy" {
  depends_on = [aws_iam_role.TranslationStateMachine_role]
  role       = aws_iam_role.TranslationStateMachine_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaRole"
}

resource "aws_iam_role_policy_attachment" "TranslationStateMachine_xray_policy" {
  depends_on = [aws_iam_role.TranslationStateMachine_role]
  role       = aws_iam_role.TranslationStateMachine_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

resource "aws_sfn_state_machine" "TranslationStateMachine" {
  depends_on = [aws_iam_role.TranslationStateMachine_role]
  name       = "Document-Translation"
  role_arn   = aws_iam_role.TranslationStateMachine_role.arn

  definition = <<EOF
{
  "StartAt": "Start order",
  "Comment": "Create initial order for translation.",
  "States": {
    "Start order": {
      "Type": "Task",
      "Resource": "${module.lambda_TranslationOrder.this_lambda_function_arn}",
      "Parameters": {
        "Payload": {
          "Input.$": "$"
        }
      },
      "Next": "Is t24 order?"
    },
    "Is t24 order?": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.translate_type",
          "StringEquals": "t24",
          "Next": "Check order. Upload doc if order is good"
        }
      ],
      "Default": "Check status. Download translation and cleanup if status = completed"
    },
    "Check order. Upload doc if order is good": {
      "Type": "Task",
      "Resource": "${module.lambda_OrderState.this_lambda_function_arn}",
      "Parameters": {
        "Payload": {
          "Input.$": "$"
        }
      },
      "Next": "Order success?"
    },
    "Order success?": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.wait",
          "NumericGreaterThan": 0,
          "Next": "Wait State order"
        }
      ],
      "Default": "Check status. Download translation and cleanup if status = completed"
    },
    "Wait State order": {
      "Type": "Wait",
      "SecondsPath": "$.wait",
      "Next": "Check order. Upload doc if order is good"
    },
    "Check status. Download translation and cleanup if status = completed": {
      "Type": "Task",
      "Resource": "${module.lambda_StatusState.this_lambda_function_arn}",
      "Parameters": {
        "Payload": {
          "Input.$": "$"
        }
      },
      "Next": "Status = completed?"
    },
    "Status = completed?": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.wait",
          "NumericGreaterThan": 0,
          "Next": "Wait State status"
        }
      ],
      "Default": "Notify"
    },
    "Wait State status": {
      "Type": "Wait",
      "SecondsPath": "$.wait",
      "Next": "Check status. Download translation and cleanup if status = completed"
    },
    "Notify": {
      "Type": "Task",
      "Resource": "${module.lambda_Notification.this_lambda_function_arn}",
      "Parameters": {
        "Payload": {
          "Input.$": "$"
        }
      },
      "End": true
    }
  }
}
EOF
}