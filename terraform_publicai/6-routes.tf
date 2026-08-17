data "aws_route_table" "rtb_private1" {
  route_table_id = "rtb-0a1ec71f56f5ce864"
}

data "aws_route_table" "rtb_private2" {
  route_table_id = "rtb-010ef690ab0503d67"
}

data "aws_route_table" "rtb_public" {
  route_table_id = "rtb-043f2d0fdd656eaf8"
}

data "aws_route_table" "rtb_unnamed" {
  route_table_id = "rtb-0c2bbfd6402ab239d"
}
