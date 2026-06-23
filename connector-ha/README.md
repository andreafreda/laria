# connector-ha

**Optional** Home Assistant adapter, over official APIs (REST + WebSocket) with a
long-lived token — not via the Supervisor.

Responsibilities:
- Read entities/states, call services.
- Subscribe to events (`subscribe_events`) → reactivity (LARIA reacts to home changes).
- Publish sensors via MQTT discovery (Lovelace dashboards update on their own).
- (Optional) one-time scaffold/update of Lovelace dashboards over WS.

If absent/disabled → LARIA still runs, with HA features turned off.
