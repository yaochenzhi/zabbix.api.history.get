ZABBIX_SERVER = "10.0.0.1"

ZABBIX_USER = {
    "user":"username",
    "password":"password",
}

ZABBIX_API_URL = "http://{}/zabbix/api_jsonrpc.php".format(ZABBIX_SERVER)

ZABBIX_API_HEADER = {"Content-Type":"application/json"}

ZABBIX_API_AUTH_TOKEN = "auth_token"