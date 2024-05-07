import stun
import requests

def get_public_ip_port():
    nat_type, external_ip, external_port = stun.get_ip_info(stun_host='stun.l.google.com', stun_port=19302)
    if(nat_type == 'Blocked'):
        print("Could not implement NAT traverse:BLOCKED")
    else:
        return external_ip, external_port

def configure_port_mapping(router_ip, username, password, external_port, internal_port, protocol='TCP'):
    url = f'http://{router_ip}/api/port_mapping'
    payload = {
        'external_port': external_port,
        'internal_port': internal_port,
        'protocol': protocol
    }
    #发送端口配置请求
    response = requests.post(url, data=payload, auth=(username, password))
    if response.status_code == 200:
        print("Port mapping configured successfully.")
    else:
        print("Failed to configure port mapping.")
