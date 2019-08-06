import configparser
import sys

import requests

from chatbot import *


# Store credentials in a separate file
def gather_credentials():
    cp = configparser.ConfigParser()
    try:
        cp.read('credentials.ini')
        cam_key = cp.get('meraki', 'key2')
        chatbot_token = cp.get('chatbot', 'token')
        user_email = cp.get('chatbot', 'email')
        org_id = cp.get('organization', 'id')
        on_tag = cp.get('organization', 'tag')
    except:
        print('Missing credentials or input file!')
        sys.exit(2)
    return cam_key, chatbot_token, user_email, org_id, on_tag


# List the devices in an organization
def get_org_devices(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    response = session.get(f'https://api.meraki.com/api/v0/organizations/{org_id}/devices', headers=headers)
    return response.json()


# List the status of every Meraki device in the organization
def get_org_statuses(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    response = session.get(f'https://api.meraki.com/api/v0/organizations/{org_id}/deviceStatuses', headers=headers)
    return response.json()


# List the networks in an organization
def get_org_networks(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    response = session.get(f'https://api.meraki.com/api/v0/organizations/{org_id}/networks', headers=headers)
    return response.json()


# Main function
if __name__ == '__main__':
    # Get credentials
    (api_key, chatbot_token, user_email, org_id, on_tag) = gather_credentials()
    session = requests.Session()

    # Get org data
    devices = get_org_devices(session, api_key, org_id)
    statuses = get_org_statuses(session, api_key, org_id)
    networks = get_org_networks(session, api_key, org_id)

    # Analyze the data
    device_serials = [d['serial'] for d in devices]
    if on_tag:
        interesting_devices = [d['serial'] for d in devices if 'tags' in d and on_tag in d['tags']]
    else:
        interesting_devices = device_serials
    online_statuses = [d['serial'] for d in statuses if d['status'] == 'online']
    net_ids = [n['id'] for n in networks]

    # Format message
    currently_down = [d for d in interesting_devices if d not in online_statuses]
    total = len(currently_down)
    if total > 0:
        plural = 'devices are' if total > 1 else 'device is'
        message = f'**{total} {plural} ❌ offline**: '
        for d in currently_down:
            device = devices[device_serials.index(d)]
            net_id = device['networkId']
            network = networks[net_ids.index(net_id)]
            if device['name']:
                message += f'  \n- _{network["name"]}_: **{device["name"]}** - {device["model"]}'
            else:
                message += f'  \n- _{network["name"]}_: **{device["mac"]}** - {device["model"]}'

    # Send message to user
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {chatbot_token}'
    }
    payload = {
        'toPersonEmail': user_email,
        'markdown': message
    }
    post_message(session, headers, payload, message)
