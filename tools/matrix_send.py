"""Send a message plus files to a Matrix room (e.g. built .flo files to your phone).

    python3 tools/matrix_send.py check
    python3 tools/matrix_send.py send "text" file...

Reads MATRIX_HOMESERVER, MATRIX_ACCESS_TOKEN and MATRIX_ROOM_ID from the env file named by
$MATRIX_ENV (default ~/credentials/matrix/relay.env). Never prints the token.
Some homeservers reject urllib's default User-Agent, so requests send their own.
"""
import json,sys,os,uuid,urllib.request,urllib.parse
from pathlib import Path
env={}
for l in Path(os.environ.get('MATRIX_ENV', Path.home()/'credentials/matrix/relay.env')).read_text().splitlines():
    if '=' in l: k,v=l.split('=',1); env[k]=v
HS=env['MATRIX_HOMESERVER']; TOK=env['MATRIX_ACCESS_TOKEN']; ROOM=env['MATRIX_ROOM_ID']
def req(method,path,body=None,ctype='application/json'):
    data=body if isinstance(body,bytes) or body is None else json.dumps(body).encode()
    r=urllib.request.Request(HS+path,data=data,method=method,headers={'Authorization':'Bearer '+TOK,'Content-Type':ctype,'User-Agent':'matrix-relay/1.0'})
    try:
        with urllib.request.urlopen(r,timeout=30) as resp: return resp.status,json.loads(resp.read() or b'{}')
    except urllib.error.HTTPError as e:
        try: err=json.loads(e.read()).get('errcode')
        except Exception: err='?'
        return e.code,{'errcode':err}
R=urllib.parse.quote(ROOM)
mode=sys.argv[1]
if mode=='check':
    print('whoami',req('GET','/_matrix/client/v3/account/whoami'))
    s,m=req('GET',f'/_matrix/client/v3/rooms/{R}/members')
    print('members',s,[(e['state_key'],e['content'].get('membership')) for e in m.get('chunk',[])] if s==200 else m)
    print('enc',req('GET',f'/_matrix/client/v3/rooms/{R}/state/m.room.encryption/')[0])
elif mode=='send':
    text=sys.argv[2]; files=sys.argv[3:]
    def send(content):
        return req('PUT',f'/_matrix/client/v3/rooms/{R}/send/m.room.message/{uuid.uuid4().hex}',content)
    print('text',send({'msgtype':'m.text','body':text}))
    for f in files:
        b=Path(f).read_bytes(); name=Path(f).name
        s,u=req('POST','/_matrix/media/v3/upload?filename='+urllib.parse.quote(name),b,'application/octet-stream')
        print('upload',name,s,u.get('errcode'))
        if s!=200: continue
        print('file',name,send({'msgtype':'m.file','body':name,'filename':name,'url':u['content_uri'],'info':{'mimetype':'application/octet-stream','size':len(b)}}))
