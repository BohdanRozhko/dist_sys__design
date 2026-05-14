#!/bin/sh
# consul-init.sh
# Seeds all configuration into Consul KV store.
# Runs once after Consul agent starts.

set -e

CONSUL="http://consul:8500"

echo "⏳ Waiting for Consul..."
until curl -sf "$CONSUL/v1/status/leader" > /dev/null; do
  sleep 2
done
echo "✅ Consul is up"

echo "📝 Writing Hazelcast config..."
curl -sf -X PUT "$CONSUL/v1/kv/hazelcast/members" \
  -d "hazelcast1:5701,hazelcast2:5701,hazelcast3:5701"

curl -sf -X PUT "$CONSUL/v1/kv/hazelcast/map_name" \
  -d "transactions"

echo "📝 Writing MQ config..."
curl -sf -X PUT "$CONSUL/v1/kv/mq/queue_name" \
  -d "transactions-queue"

echo "✅ Consul KV initialized:"
echo "   hazelcast/members  = hazelcast1:5701,hazelcast2:5701,hazelcast3:5701"
echo "   hazelcast/map_name = transactions"
echo "   mq/queue_name      = transactions-queue"
