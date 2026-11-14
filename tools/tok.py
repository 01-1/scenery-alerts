import sys,struct
d=open(sys.argv[1],'rb').read(); i=int(sys.argv[2],0); end=int(sys.argv[3],0)
def vi(i):
    r=s=0
    while True:
        b=d[i];i+=1;r|=(b&0x7f)<<s;s+=7
        if b<0x80:return r,i
out=[]
while i<end:
    st=i; v,i=vi(i)
    if v==0xd0: out.append(f'{st:x}:NUM {struct.unpack(">d",d[i:i+8])[0]}'); i+=8
    elif v in (0xd4,0xcc,0xd2,0xce,0xde) and False: pass
    elif v==0xd4: L,i=vi(i); out.append(f'{st:x}:STR {d[i:i+L][:40]!r}'); i+=L
    elif v==0xcc: L,i=vi(i); out.append(f'{st:x}:VAR {d[i:i+L].decode()}'); i+=L
    else: out.append(f'{st:x}:{v}')
print('\n'.join(out))
