## OpenWebUI chat
``chat.publicai.co`` Ask for admin access.

## Lago Billing Engine
``lago.publicai.co`` Ask for access.
``lago-api.publicai.co``

## Cloudflare
We use cloudflare to manage our domain name and DNS records.

## Monitoring
### Grafana
Go to ``grafana.publicai.co``to access the Grafana instance.

 Login details are in ``doppler: GRAFANA_ADMIN_USER GRAFANA_ADMIN_PASSWORD`` 

In Grafana there are dashboards for LiteLLM, OpenWebUI and the health-check, there are also logs for many services in the logs section.

### Prometheus
Go to ``prometheus.publicai.co`` to access the Prometheus instance.

Login details are in ``doppler: GRAFANA_ADMIN_USER GRAFANA_ADMIN_PASSWORD`` 

## AWS cloudwatch
Log in to AWS console, set the region to *Zurich eu-central-2* and search for CloudWatch.

In cloud watch go to *Dashboards*, and find a dashboard called *Overview*.

## LiteLLM
api-internal.publicai.co is the main endpoint
api-internal.publicai.co/ui is for dashboard access

username: *admin* and password in  ``doppler: LITELLM_API_KEY``. You may also have an email sign-in account.

## AWS cognito
Our auth provider for chat users is aws cognito, users acessing the platform are stored in Auth0. You will need an AWS user account ask for access, log in and search for cognito.

# API Platform
``platform.publicai.co``

## Zuplo
The platform uses Zuplo to create a billable API from our LiteLLM instance. You can access our Zuplo account at [zuplo.com](https://zuplo.com). Ask for access.

The code for the zuplo app is in another repo here: [platform.publicai.co](https://github.com/forpublicai/platform.publicai.co)

Any pushes to main will automatically be deployed, no need to access the zuplo dashboard.


## Auth0
Ask for access, finding our tenant can be tricky the url is in ``doppler: AUTH0_TENANT_URL``

## Hugging face 
Our hugging face id is ``publicai``. Ask for access. Access to this account is needed to modify our models provided to hugging face.









