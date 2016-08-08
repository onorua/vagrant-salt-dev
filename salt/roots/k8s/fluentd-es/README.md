# deploy and manage fluentd on each node

In order to deliver all logs to centralized loggin storage we use fluentd to send all container's stderr/stdout into elasticsearch. 

it will scan folder `/var/log/containers/*.log` and send data to elasticsearch configured as `elasticsearch-logging.{{dns_domain}}`
