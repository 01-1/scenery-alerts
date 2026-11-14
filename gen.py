import sys,struct,runpy
src,stops,dst,label=sys.argv[1:5]; start=int(sys.argv[5]) if len(sys.argv)>5 else 0
S=runpy.run_path(stops)['S'][start:]
d=open(src,'rb').read()
a=d.index(b'\x88\x02\x1a'); b=d.index(b')\x19Start free scenery alerts')
def v(n):
    o=b''
    while True:
        x=n&0x7f;n>>=7
        if n:o+=bytes([x|0x80])
        else:return o+bytes([x])
def s(t):t=t.encode();return b'\xd4\x01'+v(len(t))+t
def num(x):return b'\xd0\x01'+struct.pack('>d',x)
body=b'\x88\x02'+v(len(S))+b''.join(b'\x88\x02\x05'+num(la)+b'\x86\x02'+num(-lo)+num(r)+s(t)+s(x) for la,lo,r,t,x in S)
lab=label.encode()
open(dst,'wb').write(d[:a]+body+b')'+v(len(lab))+lab+d[b+2+0x19:]); print(dst,len(S),'stops')
