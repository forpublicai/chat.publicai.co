resource "aws_subnet" "private_zone_1" {
  vpc_id            = aws_vpc.main_vpc.id
  availability_zone = local.zone1
  cidr_block        = "10.0.128.0/20" # 10.0.0.0/19

  map_public_ip_on_launch = false


  tags = {
    Name                                                   = "${local.env}-private-${local.zone1}"
    "kubernetes.io/role/internal-elb"                      = "1"     # subnet can be used for private/internal load balancers
    "kubernetes.io/cluster/${local.env}-${local.eks_name}" = "owned" #
  }
}

resource "aws_subnet" "private_zone_2" {
  vpc_id            = aws_vpc.main_vpc.id
  availability_zone = local.zone2
  cidr_block        = "10.0.144.0/20" # 10.0.32.0/19

  map_public_ip_on_launch = false


  tags = {
    Name                                                   = "${local.env}-private-${local.zone2}"
    "kubernetes.io/role/internal-elb"                      = "1"     # subnet can be used for private/internal load balancers
    "kubernetes.io/cluster/${local.env}-${local.eks_name}" = "owned" #
  }
}


resource "aws_subnet" "public_zone_1" {
  vpc_id                  = aws_vpc.main_vpc.id
  cidr_block              = "10.0.0.0/20"
  availability_zone       = local.zone1
  map_public_ip_on_launch = true
  tags = {
    Name                                                   = "${local.env}-public-${local.zone1}"
    "kubernetes.io/role/elb"                               = "1" # subnet can be used for public load balancers
    "kubernetes.io/cluster/${local.env}-${local.eks_name}" = "owned"
  }
}

resource "aws_subnet" "public_zone_2" {
  vpc_id                  = aws_vpc.main_vpc.id
  cidr_block              = "10.0.16.0/20" # 10.0.90.0/19
  availability_zone       = local.zone2
  map_public_ip_on_launch = true
  tags = {
    Name                                                   = "${local.env}-public-${local.zone2}"
    "kubernetes.io/role/elb"                               = "1" # subnet can be used for public load balancers
    "kubernetes.io/cluster/${local.env}-${local.eks_name}" = "owned"
  }
}

