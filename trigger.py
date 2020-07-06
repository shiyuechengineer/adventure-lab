import meraki

from chatbot import *

SWITCH_SERIAL = 'Q2AB-1234-CDEF'
SWITCH_PORT = 8


# Disable port's PoE to trigger webhook alert
def disable_port(session, headers, payload, api_key):
    response = meraki.getswitchportdetail(api_key, SWITCH_SERIAL, SWITCH_PORT)
    if not response['enabled']:
        post_message(session, headers, payload, 'Port already disabled!')
    else:
        response = meraki.updateswitchport(api_key, SWITCH_SERIAL, SWITCH_PORT, enabled=False)
        if response['enabled']:
            post_message(session, headers, payload, 'Something went wrong!')
        else:
            post_message(session, headers, payload, 'Disabled your switchport!')


# Enable port's PoE to undo above (and trigger another webhook)
def enable_port(session, headers, payload, api_key):
    response = meraki.getswitchportdetail(api_key, SWITCH_SERIAL, SWITCH_PORT)
    if response['enabled']:
        post_message(session, headers, payload, 'Port already enabled!')
    else:
        response = meraki.updateswitchport(api_key, SWITCH_SERIAL, SWITCH_PORT, enabled=True)
        if response['enabled']:
            post_message(session, headers, payload, 'Enabled your switchport!')
        else:
            post_message(session, headers, payload, 'Something went wrong!')
