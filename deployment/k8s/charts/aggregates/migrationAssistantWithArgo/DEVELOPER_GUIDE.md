# Developer Guide
Guidance for developing components of the Migration Assistant helm chart

### Debugging Fluent Bit logs
Since Fluent Bit will also send its own pod logs to the configured destination in K8s, it can be a bit tricky to have Fluent Bit log to stdout/stderr for quick debugging as this will create a destructive loop of reading and writing its own logs by the Fluent Bit pod. A workaround for this follows where the logs for the Fluent Bit pods are ignored and a `stdout` OUTPUT is added. 

1. The existing INPUT section is modified to exclude Fluent Bit container logs
```yaml
          [INPUT]
              ...
              Exclude_Path       /var/log/containers/fluent-bit*
              ...
```
2. Add a `stdout` OUTPUT option
```yaml
          [OUTPUT]
              Name               stdout
              Match              fluentbit-*
              Format             json_lines
```
3. View the outgoing logs
```shell
kubectl -n ma logs fluent-bit-<pod_id>
```

#### Sample AWS Cloudwatch Insights Query
Sample query to see all logs from the pods that get created for a given Argo workflow run
```
fields @timestamp, level, log, pod, container, workflow, image
| filter workflow like /full-migration-<WORKFLOW_ID>/
#| filter pod like /reindex-from-snapshot/
| sort @timestamp asc 
| limit 10000
```