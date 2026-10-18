"""Coherent C1 source-informed primary surface field; no Blender mutations."""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parent
C=json.loads((ROOT/'fit/fair-body-v4.json').read_text())
P=json.loads((ROOT/'fit/surface-patches.json').read_text())

class Curve:
    def __init__(self,points):
        a=np.array(points,dtype=float);self.x=a[:,0];self.v=a[:,1]
        h=np.diff(self.x);d=np.diff(self.v)/h;m=np.zeros(len(a));m[0]=d[0];m[-1]=d[-1]
        for i in range(1,len(a)-1):
            if d[i-1]*d[i]>0:
                w1=2*h[i]+h[i-1];w2=h[i]+2*h[i-1]
                m[i]=(w1+w2)/(w1/d[i-1]+w2/d[i])
        self.m=m
    def __call__(self,x):
        x=float(np.clip(x,self.x[0],self.x[-1]));i=min(len(self.x)-2,max(0,int(np.searchsorted(self.x,x)-1)))
        h=self.x[i+1]-self.x[i];t=(x-self.x[i])/h
        return float((2*t**3-3*t*t+1)*self.v[i]+(t**3-2*t*t+t)*h*self.m[i]+
                     (-2*t**3+3*t*t)*self.v[i+1]+(t**3-t*t)*h*self.m[i+1])

RAILS={name:Curve(C[name]) for name in ['width','lower','centre','shoulder','outer']}
FRONT=C['width'][0][0];BACK=C['width'][-1][0]

def dimension(y,key):
    return RAILS['width' if key=='half_width' else key](y)

def glass_profile(y):
    for key in ('windshield','roof','rear_hatch'):
        p=P['glass_landmarks'][key];a,b=p['front_y'],p['back_y']
        if a-1e-8<=y<=b+1e-8:
            t=(y-a)/(b-a)
            return key,(1-t)*p['front_half_width']+t*p['back_half_width'],RAILS['centre'](y)-.007
    return None

def roofedge_width(y):
    if info:=glass_profile(y):return info[1]
    if y<-1.46:return float(np.interp(y,[FRONT,-1.46],[.72*dimension(FRONT,'half_width'),.88]))
    return float(np.interp(y,[1.84,BACK],[.575,.72*dimension(BACK,'half_width')]))

def shoulder(y):return RAILS['shoulder'](y)

def deck(y,fraction=0):
    w=dimension(y,'half_width');x=abs(fraction)*w;roof=roofedge_width(y);s=.91*w;outer=.993*w
    centre=RAILS['centre'](y);sh=shoulder(y);out=RAILS['outer'](y)
    if x<=roof:return centre-.007*(x/roof)**2
    if x<=s:return centre-.007+(sh-(centre-.007))*(x-roof)/(s-roof)
    return sh+(out-sh)*(x-s)/(outer-s)

def corner_setback(x,w):
    radius=.060;d=float(np.clip(abs(x)-(.993*w-radius),0,radius))
    return radius-(max(0,radius*radius-d*d))**.5

def lower_cap_rake(z):
    t=float(np.clip((.56-z)/.30,0,1))
    return .035*t*t*(3-2*t)

def surface_y(y,x,z):
    t=float(np.clip((y-FRONT)/.45,0,1));fade=1-t*t*(3-2*t)
    return y+fade*(corner_setback(x,dimension(y,'half_width'))+lower_cap_rake(z))

def front_cap_y(x,z):
    return FRONT+corner_setback(x,dimension(FRONT,'half_width'))+lower_cap_rake(z)

def body_surface_point(y,x):
    z=deck(y,abs(x)/dimension(y,'half_width'))
    return (x,surface_y(y,x,z),z)

def side_limits(y):
    polygon=C['side_glass_yz'];upper=polygon[:4];lower=[polygon[0]]+list(reversed(polygon[4:]))+[polygon[3]]
    hi=float(np.interp(y,[p[0] for p in upper],[p[1] for p in upper]))
    lo=float(np.interp(y,[p[0] for p in lower],[p[1] for p in lower]))
    return lo,hi

def plane_x(y,z):
    _,w,top=glass_profile(y);end=.91*dimension(y,'half_width')
    return w+(top-z)/(top-shoulder(y))*(end-w)

def samples(y):
    w=dimension(y,'half_width');roof=roofedge_width(y)
    return list(np.linspace(0,roof,17))+list(np.linspace(roof,.91*w,9))[1:]+list(np.linspace(.91*w,.993*w,9))[1:]
