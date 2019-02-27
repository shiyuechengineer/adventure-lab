from statistics import mean

from chatbot import *


# Call GET: https://api.meraki.com/api_docs#list-the-organizations-that-the-user-has-privileges-on
def get_organizations(session, api_key):
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = session.get(f'https://api.meraki.com/api/v0/organizations', headers=headers)
    return response.json()


# Call GET: https://api.meraki.com/api_docs#list-the-status-of-every-meraki-device-in-the-organization
def get_device_statuses(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = session.get(f'https://api.meraki.com/api/v0/organizations/{org_id}/deviceStatuses', headers=headers)

    # Filter out orgs that do not have dashboard API access enabled, on the Organization > Settings page
    if response.ok:
        return response.json()
    else:
        return None


# Call GET to new feature: /organizations/{{organizationId}}/uplinksLossAndLatency
def get_orgs_uplinks(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = session.get(f'https://api.meraki.com/api/v0/organizations/{org_id}/uplinksLossAndLatency', headers=headers)

    # Filter out orgs that do not have dashboard API access or the NFO enabled
    if response.ok:
        return response.json()
    else:
        return None


# Return device status for each org
def device_status(session, headers, payload, api_key):
    orgs = get_organizations(session, api_key)
    responded = False

    for org in orgs:

        # Skip Meraki corporate for admin users
        if org['id'] == 1:
            continue

        # Org-wide device statuses
        statuses = get_device_statuses(session, api_key, org['id'])
        if statuses:

            # Tally devices across org
            total = len(statuses)
            online_devices = [device for device in statuses if device['status'] == 'online']
            online = len(online_devices)
            alerting_devices = [device for device in statuses if device['status'] == 'alerting']
            alerting = len(alerting_devices)
            offline_devices = [device for device in statuses if device['status'] == 'offline']
            offline = len(offline_devices)

            # Format message, displaying devices names if <= 10 per section
            message = f'### **{org["name"]}**'
            if online > 0:
                message += f'  \n- {online} devices ✅ online ({online / total * 100:.1f}%)'
                if online <= 10:
                    message += ': '
                    for device in online_devices:
                        if device['name']:
                            message += f'{device["name"]}, '
                        else:
                            message += f'{device["mac"]}, '
                    message = message[:-2]

            if alerting > 0:
                message += f'  \n- _{alerting} ⚠️ alerting_ ({alerting / total * 1004:.1f}%)'
                if alerting <= 10:
                    message += ': '
                    for device in alerting_devices:
                        if device['name']:
                            message += f'{device["name"]}, '
                        else:
                            message += f'{device["mac"]}, '
                    message = message[:-2]

            if offline > 0:
                message += f'  \n- **{offline} ❌ offline** ({offline / total * 100:.1f}%)'
                if offline <= 10:
                    message += ': '
                    for device in offline_devices:
                        if device['name']:
                            message += f'{device["name"]}, '
                        else:
                            message += f'{device["mac"]}, '
                    message = message[:-2]

            post_message(session, headers, payload, message)
            responded = True

            # Show cellular failover information, if applicable
            cellular_online = [device for device in statuses if
                               'usingCellularFailover' in device and device['status'] == 'online']
            cellular = len(cellular_online)
            if cellular > 0:
                failover_online = [device for device in cellular_online if device['usingCellularFailover'] == True]
                failover = len(failover_online)

                if failover > 0:
                    post_message(session, headers, payload,
                                 f'> {failover} of {cellular} appliances online ({failover / cellular * 100:.1f}%) using 🗼 cellular failover')

        # Org-wide uplink performance
        uplinks = get_orgs_uplinks(session, api_key, org['id'])
        if uplinks:

            # Tally up uplinks with worse performance than thresholds here
            loss_threshold = 7.0
            latency_threshold = 240.0
            loss_count = 0
            latency_count = 0

            for uplink in uplinks:
                perf = uplink['timeSeries']

                loss = mean([sample['lossPercent'] for sample in perf])
                if loss > loss_threshold and loss < 100.0:  # ignore probes to unreachable IPs that are incorrectly configured
                    loss_count += 1

                latency = mean([sample['latencyMs'] for sample in perf])
                if latency > latency_threshold:
                    latency_count += 1

            if loss_count > 0:
                post_message(session, headers, payload,
                             f'{loss_count} device-uplink-probes currently have 🕳 packet loss higher than **{loss_threshold:.1f}%**!')
            if latency_count > 0:
                post_message(session, headers, payload,
                             f'{latency_count} device-uplink-probes currently have 🐢 latency higher than **{latency_threshold:.1f} ms**!')

    if not responded:
        post_message(session, headers, payload,
                     'Does your API key have access to at least a single org with API enabled? 😫')
