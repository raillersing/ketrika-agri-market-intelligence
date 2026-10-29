import json
from pathlib import Path
entries = json.loads(Path('/input.json').read_text())
result = []
for entry in entries:
    host, config = entry['HostConfig'], entry['Config']
    assert host['NetworkMode'] == 'none' and not host.get('PortBindings')
    item = {'name':entry['Name'], 'container_id':entry['Id'], 'image_id':entry['Image'],
            'state':{k:entry['State'][k] for k in ('Status','ExitCode','StartedAt','FinishedAt')},
            'network_mode':host['NetworkMode'], 'user':config['User'],
            'readonly_rootfs':host['ReadonlyRootfs'], 'cap_drop':host.get('CapDrop'),
            'security_opt':host.get('SecurityOpt'), 'port_bindings':host.get('PortBindings'),
            'mounts':[{k:m[k] for k in ('Type','Destination','RW')} | ({'name':m['Name']} if m['Type']=='volume' else {}) for m in entry['Mounts']]}
    if 'replay' in entry['Name']:
        assert config['User']=='app' and host['ReadonlyRootfs']
        assert host['CapDrop']==['ALL']
        assert all(not m['RW'] for m in entry['Mounts'] if m['Destination'] in ('/workspace','/copy','/runner.py'))
    result.append(item)
print(json.dumps({'passed':True,'scope':'kernel-independent orchestrator confinement; credentials excluded','containers':result},sort_keys=True,indent=2))
