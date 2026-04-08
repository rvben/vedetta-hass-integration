DOMAIN = "vedetta"

DEFAULT_MQTT_PREFIX = "vedetta"

CONF_MQTT_PREFIX = "mqtt_prefix"

MQTT_TOPIC_AVAILABILITY = "{prefix}/availability"
MQTT_TOPIC_CAMERA_STATUS = "{prefix}/camera/{camera}/status"
MQTT_TOPIC_OBJECT_COUNT = "{prefix}/{camera}/{label}"
MQTT_TOPIC_EVENTS = "{prefix}/events/{camera}"
MQTT_TOPIC_PRESENCE = "{prefix}/presence/{zone}/{label}"
MQTT_TOPIC_SNAPSHOT = "{prefix}/{camera}/{label}/snapshot"

ATTR_LABEL = "label"
ATTR_SCORE = "score"
ATTR_ZONE = "zone_name"
ATTR_OBJECT_NAME = "object_name"
ATTR_BOX = "box"
