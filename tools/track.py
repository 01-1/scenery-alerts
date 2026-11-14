import csv, math
R=6371000.0
def load(path='/tmp/gtfs/shape106.csv'):
    pts=[(float(r[1]),float(r[2])) for r in csv.reader(open(path))]
    ch=[0.0]
    for a,b in zip(pts,pts[1:]): ch.append(ch[-1]+hav(a,b))
    return pts,ch
def hav(a,b):
    la1,lo1,la2,lo2=map(math.radians,(a[0],a[1],b[0],b[1]))
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))
def proj_seg(p,a,b):
    # local equirectangular projection
    k=math.cos(math.radians(p[0]))
    ax,ay=(a[1]-p[1])*k,(a[0]-p[0]); bx,by=(b[1]-p[1])*k,(b[0]-p[0])
    dx,dy=bx-ax,by-ay; L=dx*dx+dy*dy
    t=0 if L==0 else max(0,min(1,-(ax*dx+ay*dy)/L))
    q=(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
    return t,q,hav(p,q)
def project(pts,ch,p,min_ch=-1e18,max_ch=1e18):
    best=None
    for i in range(len(pts)-1):
        if ch[i+1]<min_ch or ch[i]>max_ch: continue
        t,q,d=proj_seg(p,pts[i],pts[i+1])
        c=ch[i]+t*(ch[i+1]-ch[i])
        if c<min_ch: continue
        if best is None or d<best[0]: best=(d,c,q)
    return best  # (offset_m, chainage_m, point)
def project_first(pts,ch,p,min_ch,slack=300,gap=1500):
    """Closest point on the earliest pass of the track near p, at/after min_ch."""
    cands=[]
    for i in range(len(pts)-1):
        if ch[i+1]<min_ch: continue
        t,q,d=proj_seg(p,pts[i],pts[i+1]); c=ch[i]+t*(ch[i+1]-ch[i])
        if c>=min_ch: cands.append((d,c,q))
    dmin=min(x[0] for x in cands)
    near=sorted([x for x in cands if x[0]<=dmin+gap],key=lambda x:x[1])
    passes=[[near[0]]]
    for x in near[1:]:
        if x[1]-passes[-1][-1][1]>gap: passes.append([x])
        else: passes[-1].append(x)
    for ps in passes:
        b=min(ps,key=lambda x:x[0])
        if b[0]<=dmin+slack: return b
def at(pts,ch,c):
    c=max(0,min(ch[-1],c))
    lo,hi=0,len(ch)-1
    while hi-lo>1:
        m=(lo+hi)//2
        if ch[m]<=c: lo=m
        else: hi=m
    a,b=pts[lo],pts[hi]; seg=ch[hi]-ch[lo]; t=0 if seg==0 else (c-ch[lo])/seg
    return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
