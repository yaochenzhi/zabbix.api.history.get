import requests
import subprocess as commands
import traceback
import pymysql
import pickle
import copy
import time
import sys
import os
from zabbix.server.info import *


## ZABBIX INFO
#ZABBIX_SERVER = "10.0.0.1"
#
#ZABBIX_USER = {
#    "user":"username",
#    "password":"password",
#}
#
#ZABBIX_API_URL = "http://{}/zabbix/api_jsonrpc.php".format(ZABBIX_SERVER)
#ZABBIX_API_HEADER = {"Content-Type":"application/json"}
#
#ZABBIX_API_AUTH_TOKEN = "auth_token"

#
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LIST_OF_ITEMID = os.path.join(BASE_DIR, "LIST_OF_ITEMID")
LIST_OF_HOSTID_HOSTIP_HN = os.path.join(BASE_DIR, "LIST_OF_HOSTID_HOSTIP_HN")

# 
INITIAL = True if not os.path.exists(LIST_OF_ITEMID) else False


# 
time_till = int(time.time())
time_from = int(time_till - 60 * 3)


def req_zabbix(jsonrpc):
    resp = requests.post(url=ZABBIX_API_URL, json=jsonrpc, headers=ZABBIX_API_HEADER)
    try:
        result = resp.json()['result']
        return result
    except Exception as e:
        print(resp.text)
        print(traceback.format_exc(e))


def get_auth(api, user):
    """
    Get auth string for further rpc from zabbix api with user authentication info
    :type api: str
    :type user: dict(user, password)
    :rtype: str
    """
    global ZABBIX_API_AUTH_TOKEN

    if not ZABBIX_API_AUTH_TOKEN:

        params = user
        jsonrpc = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": params,
            "id": 10
        }

        ZABBIX_API_AUTH_TOKEN = req_zabbix(jsonrpc)

    print(ZABBIX_API_AUTH_TOKEN)
    return ZABBIX_API_AUTH_TOKEN


def get_jsonrpc(method, params):
    basic_jsonrpc = {
        "jsonrpc":"2.0",
        "auth": get_auth(ZABBIX_API_URL, ZABBIX_USER),
        "id":10,
    }
    jsonrpc = copy.copy(basic_jsonrpc)
    jsonrpc['method'] = method
    jsonrpc['params'] = params
    return jsonrpc


def get_groupids():

    method = "hostgroup.get"
    params = {
       "output":["groupid","name"],
    }

    jsonrpc = get_jsonrpc(method, params)

    group_ids= []
    try:
        result = req_zabbix(jsonrpc)
        for group in result:
           # print "Group ID:",group['groupid'],"\tGroupName:",group['name']
           group_ids.append(group['groupid'])

        return group_ids
    except Exception as e:
        print(traceback.format_exc(e))


def get_hostids_of_groupids(groupids, cache_host=True):
    """
    Get hostids and 
    Cache hostid - hostip - hostname info 
    :type groupids: str or str list
    :rtype: list
    """
    method = "host.get"
    params = {
       "output":["hostid","name"],
       "selectInterfaces":["ip"],
       "groupids":groupids,
    }

    jsonrpc = get_jsonrpc(method, params)

    hostids = []

    try:
        result = req_zabbix(jsonrpc)

        for host in result:
            hostids.append(host['hostid'])

        # cache host info: "hostid hostip hostname" for later hostid match
        if cache_host:
            content = ""
            for host in result:
                # print "Host ID:",host['hostid'],"HostName:",host['name'],"ip:",host['interfaces'][0]['ip']
                line = "{}\t{}\t{}\n".format(host['hostid'], host['interfaces'][0]['ip'], host['name'])
                content += line

            with open(LIST_OF_HOSTID_HOSTIP_HN, "w") as f:
                f.write(content)

        return hostids
    except Exception as e:
        print(traceback.format_exc(e))


def get_itemids_of_hostids(hostids, key_):

    method = "item.get"
    params = {
        # "output":["itemids", "hostid"]
        "output":"itemids",
        "hostids":hostids,
        "search":{
            "key_":key_
        }
    }

    jsonrpc = get_jsonrpc(method, params)

    try:
        result = req_zabbix(jsonrpc)
        return [ i['itemid'] for i in result ]
    except Exception as e:
        print(traceback.format_exc(e))


def get_history_of_itemids(itemids, time_from, time_till, history=0):

    method = "history.get"
    params = {
        "history":history,
        "itemids":itemids,
        "output":"extend",
        "time_till": time_till,
        "time_from": time_from
        # "limit":1
    }

    jsonrpc = get_jsonrpc(method, params)

    try:
        result = req_zabbix(jsonrpc)
        return result
    except Exception as e:
        print(traceback.format_exc(e))


def get_dic_of_itemid_hostid(itemids):

    dic_of_itemid_hostid = {}

    method = "item.get"
    params = {
        "output": ["hostid", "itemid"],
        "itemids": itemids
    }

    jsonrpc = get_jsonrpc(method, params)

    try:
        result = req_zabbix(jsonrpc)
        for i in result:
            dic_of_itemid_hostid[i['itemid']] = i['hostid']
        return dic_of_itemid_hostid
    except Exception as e:
        print(traceback.format_exc(e))


def get_itemids():
    """
    Get hostids of all groups and
    Cache to file
    """
    groupids = get_groupids()
    hostids = get_hostids_of_groupids(groupids)
    itemids = get_itemids_of_hostids(hostids, "system.cpu.util[,iowait]")
    with open(LIST_OF_ITEMID, "wb") as f:
        pickle.dump(itemids, f)


if __name__ == "__main__":

    # if len(sys.argv) > 1:
    #     if sys.argv[1] == "get_hostids":

    to_get_itemids = False if len(sys.argv) == 1 else False if sys.argv[1] != "get_itemids" else True

    if INITIAL or to_get_itemids:
        get_itemids()
    else:

        # target info list: error info list
        error_list = []

        error_itemid_value = {}

        with open(LIST_OF_ITEMID, "rb") as f:
            LIST_OF_ITEMID = pickle.load(f)
        history_of_itemids = get_history_of_itemids(LIST_OF_ITEMID, time_from, time_till)

        for i in history_of_itemids:
            if float(i['value']) > 10:
                error_itemid_value[i['itemid']] = i['value']

        dic_of_itemid_hostid = get_dic_of_itemid_hostid(list(error_itemid_value))
        
        for itemid in error_itemid_value:
            hostid = dic_of_itemid_hostid[itemid]
            itemid_v = error_itemid_value[itemid]
            line = commands.getoutput("grep -w {} {} | head -1".format(hostid, LIST_OF_HOSTID_HOSTIP_HN))
            hostid, hostip, hostname = line.strip().split()

            error_list.append([hostid, hostip, hostname, itemid_v])

        print(error_list)

#<<< END
