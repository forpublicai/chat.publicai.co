data "aws_subnet" "private_zone_1" {
  id = "subnet-09958276ecaa0f874"
}

data "aws_subnet" "private_zone_2" {
  id = "subnet-01c62df025055d755"
}

data "aws_subnet" "private_zone_3" {
  id = "subnet-00482826220dd1207"
}

data "aws_subnet" "public_zone_1" {
  id = "subnet-0483ba7b0f6e163fa"
}

data "aws_subnet" "public_zone_2" {
  id = "subnet-0b21f6615b27fca69"
}
