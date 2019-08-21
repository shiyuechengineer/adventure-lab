import time

from chatbot import *


# For Meraki network, return cameras' snapshots (optionally only for filtered cameras)
def meraki_snapshots(session, api_key, net_id, timestamp=None, filters=None):
    # Get devices of network and filter for MV cameras
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    response = session.get(f'https://api.meraki.com/api/v0/networks/{net_id}/devices', headers=headers)
    devices = response.json()
    cameras = [device for device in devices if device['model'][:2] == 'MV']

    # Assemble return data
    snapshots = []
    for camera in cameras:
        # Remove any cameras not matching filtered names
        name = camera['name'] if 'name' in camera else camera['mac']
        tags = camera['tags'] if 'tags' in camera else ''
        tags = tags.split()
        if filters and name not in filters and not set(filters).intersection(tags):
            continue

        # Get video link
        if timestamp:
            response = session.get(
                f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{camera["serial"]}/videoLink?timestamp={timestamp}',
                headers=headers)
        else:
            response = session.get(
                f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{camera["serial"]}/videoLink',
                headers=headers)
        video_link = response.json()['url']

        # Get snapshot link
        if timestamp:
            response = session.post(
                f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{camera["serial"]}/snapshot',
                headers=headers,
                json={'timestamp': timestamp})
        else:
            response = session.post(
                f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{camera["serial"]}/snapshot',
                headers=headers)

        # Possibly no snapshot if camera offline, photo not retrievable, etc.
        if response.ok:
            snapshots.append((name, response.json()['url'], video_link))
        else:
            snapshots.append((name, None, video_link))

    return snapshots


# Determine whether to retrieve all cameras or just selected snapshots
def return_snapshots(session, headers, payload, api_key, net_id, message, cameras):
    try:
        # All cameras
        if message_contains(message, ['all', 'complete', 'entire', 'every', 'full']):
            post_message(session, headers, payload,
                         '📸 _Retrieving all cameras\' snapshots..._')
            snapshots = meraki_snapshots(session, api_key, net_id, None, None)

        # Or just specified/filtered ones
        else:
            post_message(session, headers, payload,
                         '📷 _Retrieving camera snapshots..._')
            snapshots = meraki_snapshots(session, api_key, net_id, None, cameras)

        # Send cameras names with files (URLs)
        for (name, snapshot, video) in snapshots:
            if snapshot:
                attempts = 10
                while attempts > 0:
                    r = session.get(snapshot, stream=True)
                    if r.ok:
                        print(f'Retried {10 - attempts} times')
                        temp_file = f'/tmp/{name}.jpg'
                        with open(temp_file, 'wb') as f:
                            for chunk in r:
                                f.write(chunk)

                        # Send snapshot without analysis
                        send_file(session, headers, payload, f'[{name}]({video})', temp_file, file_type='image/jpg')

                        # Analyze & send snapshot
                        pass

                        break
                    else:
                        time.sleep(1)
                        attempts -= 1
                # Snapshot GET with URL did not return any image
                if attempts == 0:
                    post_message(session, headers, payload,
                                 f'GET error with snapshot for camera **{name}**')
            else:
                # Snapshot POST was not successful in retrieving image URL
                post_message(session, headers, payload,
                             f'POST error with snapshot for camera **{name}**')
    except:
        post_message(session, headers, payload,
                     'Does your API key have write access to the specified network ID with cameras? 😳')
