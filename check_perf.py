import configparser
import sys

import requests

from chatbot import *

LOSS_THRESHOLD = 7.0
LATENCY_THRESHOLD = 49.0

# Store credentials in a separate file
def gather_credentials():
    cp = configparser.ConfigParser()
    try:
        cp.read('credentials.ini')
        cam_key = cp.get('meraki', 'key2')
        chatbot_token = cp.get('chatbot', 'token')
        user_email = cp.get('chatbot', 'email')
        org_id = cp.get('meraki', 'organization')
        perf_tag = cp.get('meraki', 'tag2')
    except:
        print('Missing credentials or input file!')
        sys.exit(2)
    return cam_key, chatbot_token, user_email, org_id, perf_tag


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


# Return the uplink loss and latency for every MX in the organization from at latest 2 minutes ago
def get_appliance_perf(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    response = session.get(f'https://api.meraki.com/api/v0/organizations/{org_id}/uplinksLossAndLatency', headers=headers)
    return response.json()


# Main function
if __name__ == '__main__':
    # Get credentials
    (api_key, chatbot_token, user_email, org_id, perf_tag) = gather_credentials()
    session = requests.Session()

    # Webex Teams data
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {chatbot_token}'
    }
    payload = {
        'toPersonEmail': user_email
    }

    # Get org data
    devices = get_org_devices(session, api_key, org_id)
    statuses = get_org_statuses(session, api_key, org_id)
    networks = get_org_networks(session, api_key, org_id)
    perf = get_appliance_perf(session, api_key, org_id)

    # Analyze the data
    device_serials = [d['serial'] for d in devices]
    network_ids = [n['id'] for n in networks]
    if perf_tag:
        interesting_devices = [d['serial'] for d in devices if 'tags' in d and perf_tag in d['tags'] and d['model'][:2] in ('MX', 'Z1', 'Z3')]
    else:
        interesting_devices = [d['serial'] for d in devices if d['model'][:2] in ('MX', 'Z1', 'Z3')]

    # Calculate average loss and latency across all probes for last 5 minutes, for given appliance's uplink
    for serial in interesting_devices:
        data = [p for p in perf if p['serial'] == serial]
        data_wan1 = [u for u in data if u['uplink'] == 'wan1']
        data_wan2 = [u for u in data if u['uplink'] == 'wan2']
        for (wan_data, text) in [(data_wan1, 'WAN1'), (data_wan2, 'WAN2')]:
            if wan_data:
                total_loss  = 0
                total_latency = 0
                for tuple in wan_data:
                    for sample in tuple['timeSeries']:
                        total_loss += sample['lossPercent']
                        total_latency += sample['latencyMs']
                average_loss = total_loss / len(wan_data) / 5
                average_latency = total_latency / len(wan_data) / 5

                # High packet loss
                if average_loss > LOSS_THRESHOLD:
                    # Format message®
                    device_name = devices[device_serials.index(serial)]['name']
                    model = devices[device_serials.index(serial)]['model']
                    net_id = devices[device_serials.index(serial)]['networkId']
                    network_name = networks[network_ids.index(net_id)]['name']

                    # Send message to user
                    message = f'🕳 **{device_name}** ({model}) in _{network_name}_ has packet loss of **{average_loss:.1f}%** on _{text}_'
                    post_message(session, headers, payload, message)

                # High latency
                if average_latency > LATENCY_THRESHOLD:
                    # Format message
                    device_name = devices[device_serials.index(serial)]['name']
                    model = devices[device_serials.index(serial)]['model']
                    net_id = devices[device_serials.index(serial)]['networkId']
                    network_name = networks[network_ids.index(net_id)]['name']

                    # Send message to user
                    message = f'🐢 **{device_name}** ({model}) in _{network_name}_ has latency of **{average_latency:.1f} ms** on _{text}_'
                    post_message(session, headers, payload, message)
