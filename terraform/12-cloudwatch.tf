resource "aws_cloudwatch_dashboard" "overview" {
  dashboard_name = "${local.env}-${local.org}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 2
        width  = 24
        height = 1
        properties = {
          markdown   = "# Load balancer"
          background = "transparent"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 3
        width  = 9
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName=\"RequestCount\"', 'Sum', 300)"
              }
            ]
          ]
          legend   = { position = "bottom" }
          title    = "RequestCount: Sum (Traffic volume)"
          region   = local.region
          liveData = false
          timezone = "UTC"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 9
        y      = 3
        width  = 7
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName=\"TargetResponseTime\"', 'Average', 300)"
              }
            ]
          ]
          legend   = { position = "bottom" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "TargetResponseTime: Average (backend latency)"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 3
        width  = 8
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName=\"ActiveConnectionCount\"', 'Sum', 300)"
              }
            ]
          ]
          legend   = { position = "bottom" }
          title    = "ActiveConnectionCount: Sum"
          region   = local.region
          liveData = false
          timezone = "UTC"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 9
        width  = 9
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName=\"RejectedConnectionCount\"', 'Sum', 300)"
              }
            ]
          ]
          legend   = { position = "bottom" }
          title    = "RejectedConnectionCount: Sum"
          region   = local.region
          liveData = false
          timezone = "UTC"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 9
        y      = 9
        width  = 7
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName=\"HTTPCode_ELB_5XX_Count\"', 'Sum', 300)"
              }
            ]
          ]
          legend   = { position = "bottom" }
          title    = "HTTPCode_ELB_5XX_Count: Sum"
          region   = local.region
          liveData = false
          timezone = "UTC"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 9
        width  = 8
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName=\"HTTPCode_ELB_4XX_Count\"', 'Sum', 300)"
              }
            ]
          ]
          legend   = { position = "bottom" }
          title    = "HTTPCode_ELB_4XX_Count: Sum"
          region   = local.region
          liveData = false
          timezone = "UTC"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "text"
        x      = 0
        y      = 15
        width  = 24
        height = 1
        properties = {
          markdown   = "# Database"
          background = "transparent"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 16
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_1.identifier, { period = 300, stat = "Average" }],
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_2.identifier, { period = 300, stat = "Average" }]
          ]
          legend   = { position = "bottom" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "DB CPUUtilization: Average (DB load)"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 16
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_1.identifier, { period = 300, stat = "Sum" }],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_2.identifier, { period = 300, stat = "Sum" }]
          ]
          legend   = { position = "bottom" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "DatabaseConnections: Sum (check exhaustion)"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 16
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "FreeableMemory", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_1.identifier, { period = 300, stat = "Average" }],
            ["AWS/RDS", "FreeableMemory", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_2.identifier, { period = 300, stat = "Average" }]
          ]
          legend   = { position = "bottom" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "DB FreeableMemory: Average (close to 0 is bad)"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 18
        y      = 16
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_1.identifier, { period = 300, stat = "Average" }],
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_rds_cluster_instance.instance_2.identifier, { period = 300, stat = "Average" }]
          ]
          legend   = { position = "bottom" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "DB FreeStorageSpace: Average"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 22
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "Deadlocks", { period = 60 }]
          ]
          region = local.region
          title  = "DB Deadlocks"
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 22
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "CommitLatency", "DBClusterIdentifier", aws_rds_cluster.this.cluster_identifier, { period = 60 }],
            [".", "WriteLatency", ".", ".", { period = 60 }],
            [".", "ReadLatency", ".", ".", { period = 60 }]
          ]
          region = local.region
          title  = "DB CommitLatency, ReadLatency, WriteLatency"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 22
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "DiskQueueDepth", { period = 60 }]
          ]
          region = local.region
          title  = "DB DiskQueueDepth"
        }
      },
      {
        type   = "metric"
        x      = 18
        y      = 22
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "AuroraReplicaLag", { period = 60 }]
          ]
          region = local.region
          title  = "DB AuroraReplicaLag"
        }
      },
      {
        type   = "text"
        x      = 0
        y      = 28
        width  = 24
        height = 1
        properties = {
          markdown = "# Cluster"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 3
        height = 2
        properties = {
          sparkline = true
          metrics = [
            [
              {
                expression = "RUNNING_SUM(m2)"
                label      = "Expression1"
                id         = "e1"
              }
            ],
            [
              "AWS/Cognito", "SignUpSuccesses",
              "UserPool", aws_cognito_user_pool.this.id,
              "UserPoolClient", aws_cognito_user_pool_client.publicai_app.id,
              {
                id      = "m2"
                visible = false
              }
            ]
          ]
          view    = "singleValue"
          stacked = false
          region  = local.region
          stat    = "Average"
          period  = 300
          title   = "SignUpSuccesses"
        }
      },
      {
        type   = "metric"
        x      = 3
        y      = 0
        width  = 3
        height = 2
        properties = {
          sparkline = true
          metrics = [
            [
              {
                expression = "RUNNING_SUM(m1)"
                label      = "Expression1"
                id         = "e1"
              }
            ],
            [
              "AWS/Cognito", "SignInSuccesses",
              "UserPool", aws_cognito_user_pool.this.id,
              "UserPoolClient", aws_cognito_user_pool_client.publicai_app.id,
              {
                id      = "m1"
                visible = false
              }
            ]
          ]
          view    = "singleValue"
          stacked = false
          region  = local.region
          stat    = "Average"
          period  = 300
          title   = "SignInSuccesses"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 29
        width  = 6
        height = 6
        properties = {
          metrics = [
            ["AWS/EKS", "apiserver_request_total_4XX", "ClusterName", aws_eks_cluster.eks.name, { period = 300, stat = "Sum" }],
            ["AWS/EKS", "apiserver_request_total_5XX", "ClusterName", aws_eks_cluster.eks.name, { period = 300, stat = "Sum" }]
          ]
          legend   = { position = "bottom" }
          title    = "API Server Error Rates"
          yAxis    = { left = { showUnits = false, label = "Count" } }
          region   = local.region
          liveData = false
          timezone = "UTC"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 29
        width  = 10
        height = 6
        properties = {
          sparkline = true
          metrics = [
            [
              {
                expression = "SUM(METRICS())"
                label      = "Expression1"
                id         = "e1"
                visible    = false
              }
            ],
            ["AWS/EKS", "scheduler_schedule_attempts_UNSCHEDULABLE", "ClusterName", aws_eks_cluster.eks.name, { id = "m1" }],
            [".", "scheduler_schedule_attempts_ERROR", ".", ".", { id = "m4" }],
            [".", "scheduler_pending_pods_UNSCHEDULABLE", ".", ".", { id = "m2" }],
            [".", "scheduler_pending_pods_BACKOFF", ".", ".", { id = "m3" }],
            [".", "scheduler_pending_pods_GATED", ".", ".", { id = "m5" }]
          ]
          view    = "singleValue"
          stacked = false
          region  = local.region
          stat    = "Average"
          period  = 300
          title   = "Scheduler problems"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 29
        width  = 8
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/EC2,InstanceId} MetricName=\"CPUUtilization\" \"kubernetes.io/cluster/${aws_eks_cluster.eks.name}\"', 'Average', 300)"
              }
            ]
          ]
          legend   = { position = "right" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "CPU Utilization: Average"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "text"
        x      = 0
        y      = 35
        width  = 24
        height = 1
        properties = {
          markdown = "# Storage"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 36
        width  = 12
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/EBS,VolumeId} MetricName=\"VolumeTotalReadTime\"', 'Average', 300)"
              }
            ]
          ]
          legend   = { position = "right" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "VolumeTotalReadTime: Average"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 36
        width  = 12
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SEARCH('{AWS/EBS,VolumeId} MetricName=\"VolumeTotalWriteTime\"', 'Average', 300)"
              }
            ]
          ]
          legend   = { position = "right" }
          region   = local.region
          liveData = false
          timezone = "UTC"
          title    = "VolumeTotalWriteTime: Average"
          view     = "timeSeries"
          stacked  = false
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 42
        width  = 12
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SELECT AVG(BucketSizeBytes)\nFROM SCHEMA(\"AWS/S3\", BucketName, StorageType)\nWHERE BucketName = '${aws_s3_bucket.bucket.id}'\nGROUP BY StorageType\nORDER BY AVG() DESC"
                label      = "$${LABEL} [avg: $${AVG}]"
                id         = "q1"
              }
            ]
          ]
          legend  = { position = "bottom" }
          period  = 3600
          view    = "timeSeries"
          stacked = false
          title   = "Total bucket size"
          region  = local.region
          yAxis   = { left = { showUnits = false }, right = { showUnits = false } }
          stat    = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 42
        width  = 12
        height = 6
        properties = {
          metrics = [
            [
              {
                expression = "SELECT AVG(NumberOfObjects)\nFROM SCHEMA(\"AWS/S3\", BucketName, StorageType)\nWHERE BucketName = '${aws_s3_bucket.bucket.id}'\nGROUP BY StorageType\nORDER BY AVG() DESC"
                label      = "$${LABEL} [avg: $${AVG}]"
                id         = "q2"
              }
            ]
          ]
          legend  = { position = "bottom" }
          period  = 3600
          view    = "timeSeries"
          stacked = false
          title   = "Total number of objects"
          region  = local.region
          yAxis   = { left = { showUnits = false }, right = { showUnits = false } }
          stat    = "Average"
        }
      }
    ]
  })
}
