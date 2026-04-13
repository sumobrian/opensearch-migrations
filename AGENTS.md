# AGENTS.md

## Cursor Cloud specific instructions

### Overview
OpenSearch Migration Assistant is a Gradle multi-project (Java 11-17) with Python (console_link CLI/API), TypeScript/Node.js (frontend, CDK), and Docker containers. The Gradle wrapper (`./gradlew`) at the repo root is the primary build tool.

### Prerequisites (installed in VM snapshot)
- **JDK 17** (Amazon Corretto) — set as default; `JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto`
- **JDK 11** (Amazon Corretto) — auto-selected by Gradle toolchain for the capture proxy subproject
- **Docker CE** — with fuse-overlayfs storage driver and iptables-legacy for DinD support
- **Python 3.11** — required by Pipfile lockfiles; also Python 3.12 available as system default
- **pipenv** — installed in `~/.local/bin`; ensure `PATH` includes it
- **Node.js v22** — downloaded automatically by Gradle when needed

### Build commands
- `./gradlew build -x test` — compile all Java artifacts (skip tests for faster iteration)
- `./gradlew spotlessCheck` — lint check (Spotless for Java formatting)
- `./gradlew spotlessApply` — auto-fix lint issues
- `./gradlew test` — run unit tests (excludes `longTest` and `isolatedTest` tags)
- `./gradlew :coreUtilities:test` — run tests for a specific subproject

### Docker Compose E2E environment
From the repo root:
```
./gradlew :TrafficCapture:dockerSolution:composeUp
./gradlew :TrafficCapture:dockerSolution:composeDown
```

### Important caveats

1. **Docker daemon must be started manually:** Run `sudo dockerd &>/tmp/dockerd.log &` and wait a few seconds before Docker commands work. Also ensure docker socket permissions: `sudo chmod 666 /var/run/docker.sock`.

2. **Pipfile.lock freshness:** Docker image builds use `pipenv install --deploy`, which requires Pipfile.lock to match exactly. If builds fail with `DeployException`, regenerate locks:
   ```
   find . -name Pipfile -not -path "*/cdk.out/*" | while read pipfile; do
     dir=$(dirname "$pipfile")
     (cd "$dir" && PIPENV_IGNORE_VIRTUALENVS=1 pipenv lock --python 3.11)
   done
   ```

3. **OpenAPI/frontend tasks:** The `:console_link:buildOpenApiDockerImage` and `:frontend:build` tasks have a dependency chain through OpenAPI spec generation. If they fail, exclude them:
   ```
   ./gradlew build -x :console_link:buildOpenApiDockerImage -x :console_link:generateOpenApiSpec -x :frontend:generateBackendClient -x :frontend:build
   ```

4. **Cluster credentials:**
   - Source ES (capture proxy at `:9200`, direct at `:19200`): `admin:admin`
   - Target OpenSearch (`:29200`): `admin:myStrongPassword123!`

5. **Traffic replay verification:** After indexing data through the capture proxy (port 9200), wait a few seconds, then verify the same data appears on the target cluster (port 29200) with the target credentials.

6. **`JAVA_HOME` must be set** to `/usr/lib/jvm/java-17-amazon-corretto` before running Gradle commands.
