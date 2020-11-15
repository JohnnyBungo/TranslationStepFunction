variable "aws_region" {
  description = "AWS region to launch the ressources."
  default     = "eu-west-2"
}

variable "accountId" {
  description = "Account-ID"
  default     = "566355141541"
}

variable "input_bucket" {
  description = "S3 for documents to translate"
  default     = "doc-raitranslate-inputs"
}

variable "t24prefix" {
  description = "Test or real API?"
  default     = "https://api-test.24t.net/"
  #default      = "https://api.24translate.ch/""
}