# static ip for nat gateway
resource "aws_eip" "nat_eip" {
  domain                    = "vpc"

  tags = {
    Name = "${local.env}-nat-eip"
  }
}

resource "aws_nat_gateway" "nat_gateway" {
  allocation_id = aws_eip.nat_eip.id
  subnet_id = aws_subnet.public_zone_1.id

   tags = {
    Name = "${local.env}-nat-gateway"
  }

  depends_on = [aws_internet_gateway.igw]
}