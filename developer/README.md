# Local Developer Setup: External Databases & Kubernetes Integration

This directory contains the configurations required to run a local development database and caching layer (PostgreSQL + Redis) in Docker Compose, and hook them up to Kubernetes (k0s) services (Lago, OpenWebUI, LiteLLM) deployed via `./web-services.sh`.

---

## Architecture Overview

This setup runs the datastores on the host machine using Docker Compose and exposes them to Kubernetes pods via stable Kubernetes Services (`external-postgres` and `external-redis`) mapped to the host's k0s network bridge IP (`10.244.0.1`).

```
+--------------------------------------------------------+
|                      HOST MACHINE                      |
|                                                        |
|  +--------------------+      +----------------------+  |
|  |   Docker Compose   |      |  K0s Local Cluster   |  |
|  |                    |      |                      |  |
|  |  [Postgres DB]     | <----+ [external-postgres]  |  |
|  |  (Lago, LiteLLM,   |      |      Service         |  |
|  |   OpenWebUI DBs)   |      |                      |  |
|  |                    |      |  [external-redis]    |  |
|  |  [Redis Cache]     | <----+      Service         |  |
|  |                    |      |                      |  |
|  |  [pgAdmin 4]       |      |  [Lago / LiteLLM /   |  |
|  |                    |      |   OpenWebUI Pods]    |  |
|  +--------------------+      +----------------------+  |
+--------------------------------------------------------+
```

---

## Prerequisites

Ensure you have the following installed on your machine:
* **Docker & Docker Compose**
* **kubectl & Helm**

---

## Setup
### Create a k0s disk
Make a directory for k0s disk on your local machine.
```bash
mkdir /k0sdisk
```

### Generate the Environment File
`generate-env.sh` automatically creates a local `.env` file with randomized secret keys (including JWT salts, encryption keys, and a Base64-encoded RSA private key for Lago) and default database credentials.

```bash
./generate-env.sh
```

### Step 2: Spin Up the Databases & Caching
Start the PostgreSQL database, Redis, and pgAdmin containers in the background:
```bash
docker compose up -d
```
*   **PostgreSQL 15** uses `getlago/postgres-partman:15.0-alpine` to satisfy Lago's requirement for the `pg_partman` partitioning extension.
*   The DB automatically executes `init-db.sql` on startup to initialize the `litellm` and `openwebui` databases and roles.
*   Verify that they are healthy:
    ```bash
    docker compose ps
    ```

You can access PGAdmin on 127.0.0.1:15433

```
PGADMIN_DEFAULT_EMAIL=admin@publicai.co
PGADMIN_DEFAULT_PASSWORD=password
```

The password for each database is ``password``


### Install K8s
THis will install k0s on your local machine, set up storage and install services to connect to the dbs running in docker.
```bash
install-k8s.sh
```
The cluster will be named ``publicai-local`` in your kube config.

You cn now use ``kubectl`` to interact with the cluster. Or use headlamp:

```bash
flatpak install io.kinvolk.Headlamp
flatpak run io.kinvolk.Headlamp
```

### Run the Helm Chart Deployment
Deploy the web services (Lago, LiteLLM, OpenWebUI) using the developer deployment script:
```bash
./web-services.sh --deploy-all
```
This loads variables from the newly created `.env` file and installs the Helm charts.

---

## Datastore Credentials

### PostgreSQL Databases

| Service | Database Name | User | Password   | Host Port |
| :--- | :--- | :--- |:-----------| :--- |
| **Lago** | `lago` | `lago` | `password` | `5432` |
| **LiteLLM** | `litellm` | `llmproxy` | `password` | `5432` |
| **OpenWebUI** | `openwebui` | `openwebui` | `password` | `5432` |

### Redis Databases (Logical Index)

*   **Lago:** `redis://external-redis:6379/0`
*   **LiteLLM:** `redis://external-redis:6379/1`
*   **OpenWebUI:** `redis://external-redis:6379/2`

---

## Database Management (pgAdmin)

pgAdmin 4 is included in this setup to manage your local databases. 
*   **URL:** `http://localhost:15433`
*   **Default Username:** `admin@publicai.co`
*   **Default Password:** `password`

*Note: The `servers.json` file is mounted into the container to automatically register and group all three databases under "PublicAI Services" upon your first login.*

---

## Troubleshooting

### Reset docker compose

```bash
# Stop the containers and remove them along with the network
docker compose down

# Delete the named volumes created by the compose file
docker volume rm developer_lago_postgres_data developer_lago_redis_data developer_pgadmin_data
```


### 1. Permission Denied on `pgadmin-data`
If you modify pgAdmin to mount a local directory rather than a named volume, pgAdmin (running as UID `5050` inside the container) might fail to write to the host system.
*   **Fix:** Ensure you are using the named volume `pgadmin_data` (default in the updated `compose.yaml`).

### 2. Port Conflicts
If you have local instances of Postgres or Redis running on your machine natively (outside Docker), Docker Compose may fail to bind to `5432` or `6379`.
*   **Fix:** Stop the native host services (e.g., `sudo systemctl stop postgresql` and `sudo systemctl stop redis`) before running `docker compose up -d`.
