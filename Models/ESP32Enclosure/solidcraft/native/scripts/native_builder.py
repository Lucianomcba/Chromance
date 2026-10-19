"""Native SolidCraft command authoring; no imported geometry or CAD kernel."""
from __future__ import annotations
from dataclasses import dataclass
import json,math,re,subprocess,tempfile
from pathlib import Path
from parameter_ranges import RANGES,NATIVE_NAMES

@dataclass(frozen=True)
class E:
    text:str
    value:float
    def _op(self,other,op,fn):
        other=expr(other);return E(f'({self.text}){op}({other.text})',fn(self.value,other.value))
    def __add__(self,o):return self._op(o,'+',lambda a,b:a+b)
    def __radd__(self,o):return expr(o).__add__(self)
    def __sub__(self,o):return self._op(o,'-',lambda a,b:a-b)
    def __rsub__(self,o):return expr(o).__sub__(self)
    def __mul__(self,o):return self._op(o,'*',lambda a,b:a*b)
    def __rmul__(self,o):return expr(o).__mul__(self)
    def __truediv__(self,o):return self._op(o,'/',lambda a,b:a/b)
    def __rtruediv__(self,o):return expr(o).__truediv__(self)
    def __neg__(self):return E(f'-({self.text})',-self.value)
    def __pow__(self,o):return self._op(o,'^',lambda a,b:a**b)

def expr(x):return x if isinstance(x,E) else E(str(x),float(x))
def val(x):return expr(x).value
def datum(x):return expr(x).text if isinstance(x,E) else x
def sqrt(x):x=expr(x);return E(f'sqrt({x.text})',math.sqrt(x.value))
def atan2(y,x):y,x=expr(y),expr(x);return E(f'atan2({y.text},{x.text})',math.degrees(math.atan2(y.value,x.value)))
def tan(x):x=expr(x);return E(f'tan({x.text})',math.tan(math.radians(x.value)))
def maximum(a,b):a,b=expr(a),expr(b);return E(f'max({a.text},{b.text})',max(a.value,b.value))
def minimum(a,b):a,b=expr(a),expr(b);return E(f'min({a.text},{b.text})',min(a.value,b.value))

def serialize(x):
    if isinstance(x,E):return x.text
    if isinstance(x,dict):return {k:serialize(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [serialize(v) for v in x]
    return x

class Builder:
    def __init__(self,defaults):
        self.commands=[];self.names=set();self.bodies=set();self.p={};self.defaults=defaults;self.counter=0;self.part_bodies={}
        self.cmd('document.inspect',measure=False,sketches=False)
        for name,value in defaults.items():
            unit='deg' if name in ('vent_angle','lid_corner_support_angle') else 'mm'
            low,high=RANGES.get(name,(value,value))
            comment=f'Allowed range: {low:g} to {high:g} {unit}; vary one input at a time from defaults. '+('Measured/hardware or design reference; nominal value only is validated.' if low==high else 'Native edit range; verify the saved validation report before printing.')
            self.parameter(name,value,unit=unit,comment=comment)
            if name in RANGES:self.cmd('parameters.favorite',name=NATIVE_NAMES.get(name,name),favorite=True)
    def cmd(self,command,/,**params):
        if command.startswith(('solid.','sketch.create')) and 'name' in params:
            if params['name'] in self.names:raise ValueError('Repeated feature '+params['name'])
            self.names.add(params['name'])
        self.commands.append({'command':command,'params':serialize(params)})
    def parameter(self,name,value,unit='mm',comment='Derived expression; follows its driving parameters.'):
        if name in self.p:return self.p[name]
        if isinstance(value,E):code=value.text;n=value.value
        else:code=f'{value} {unit}' if unit else str(value);n=float(value)
        native_name=NATIVE_NAMES.get(name,name)
        self.cmd('parameters.add',name=native_name,expression=code,unit=unit,comment=comment)
        self.p[name]=E(native_name,n);return self.p[name]
    def derived(self,name,value,unit='mm'):return self.parameter(name,value,unit=unit)
    def _target(self,body,op):
        if op=='new':
            if body in self.bodies:raise ValueError('Repeated body '+body)
            self.bodies.add(body);return {'operation':'new','body_name':body}
        return {'operation':op,'targets':[body]} if body is not None else {'operation':op}
    def polygon(self,name,points,height,*,body,op='join',plane='XY',offset=0,symmetric=False):
        pts=[[val(x),val(y)] for x,y in points]
        self.cmd('sketch.create',plane=plane,offset=offset,name=name+'_profile')
        self.cmd('sketch.line',points=pts,closed=True,infer=False,connect=False)
        n=len(points)
        self.cmd('sketch.point',point=[-200,-200])
        self.cmd('sketch.constraint.fix',entity='p1')
        references=['l1.start']+[f'l{i}.end' for i in range(1,n)]
        for reference,(x,y) in zip(references,points):
            self.cmd('sketch.dimension',entities=['p1',reference],type='horizontal',value=200+expr(x))
            self.cmd('sketch.dimension',entities=['p1',reference],type='vertical',value=200+expr(y))
        self.cmd('sketch.solve');self.cmd('sketch.finish')
        self.cmd('solid.extrude',distance=height,direction='symmetric' if symmetric else 'positive',name=name,**self._target(body,op))
        return body
    def box(self,name,w,d,h,x=0,y=0,z=0,*,body,op='join'):
        return self.polygon(name,[(x-w/2,y-d/2),(x+w/2,y-d/2),(x+w/2,y+d/2),(x-w/2,y+d/2)],h,body=body,op=op,offset=z)
    def cavity(self,name,outline,rectangles,circles,z,height,body,points=None):
        self.cmd('sketch.create',plane='XY',offset=z,name=name+'_profile')
        self.cmd('sketch.point',point=[-200,-200]);self.cmd('sketch.constraint.fix',entity='p1')
        count=0
        for polygon_points in [outline]+rectangles:
            first=count+1
            self.cmd('sketch.line',points=[[val(x),val(y)] for x,y in polygon_points],closed=True,infer=False,connect=False)
            refs=[f'l{first}.start']+[f'l{first+j}.end' for j in range(len(polygon_points)-1)]
            for ref,(x,y) in zip(refs,polygon_points):
                self.cmd('sketch.dimension',entities=['p1',ref],type='horizontal',value=200+expr(x))
                self.cmd('sketch.dimension',entities=['p1',ref],type='vertical',value=200+expr(y))
            count+=len(polygon_points)
        for i,(x,y,r) in enumerate(circles,1):
            self.cmd('sketch.circle.center',center=[val(x),val(y)],radius=val(r),connect=False)
            self.cmd('sketch.dimension',entities=[f'c{i}'],type='diameter',value=2*r)
            self.cmd('sketch.dimension',entities=['p1',f'c{i}.center'],type='horizontal',value=200+expr(x))
            self.cmd('sketch.dimension',entities=['p1',f'c{i}.center'],type='vertical',value=200+expr(y))
        self.cmd('sketch.solve');self.cmd('sketch.finish')
        self.cmd('solid.extrude',profiles=[{'point':[val(x),val(y)]} for x,y in (points or [(0,0)])],distance=height,name=name,**self._target(body,'cut'))
    def box_circle(self,name,w,d,h,x,y,z,cx,cy,r,*,body,op='join'):
        # All arrangement regions of crossing loops form one planar union. This
        # avoids introducing coincident cylindrical faces via a later 3D union.
        start=len(self.commands)
        self.box(name,w,d,h,x,y,z,body=body,op=op)
        finish=next(i for i in range(start,len(self.commands)) if self.commands[i]['command']=='sketch.solve')
        following=self.commands[finish:];self.commands=self.commands[:finish]
        self.cmd('sketch.circle.center',center=[val(cx),val(cy)],radius=val(r),connect=False)
        self.cmd('sketch.dimension',entities=['c1'],type='diameter',value=2*r)
        self.cmd('sketch.dimension',entities=['p1','c1.center'],type='horizontal',value=200+expr(cx))
        self.cmd('sketch.dimension',entities=['p1','c1.center'],type='vertical',value=200+expr(cy))
        self.commands.extend(following)
    def cylinder(self,name,r,h,x=0,y=0,z=0,*,body,op='cut',axis='Z'):
        plane,offset,uv={'Z':('XY',z,(x,y)),'X':('YZ',x,(y,z)),'Y':('XZ',y,(x,-expr(z)))}[axis]
        self.cmd('sketch.create',plane=plane,offset=offset,name=name+'_profile')
        self.cmd('sketch.circle.center',center=[val(a) for a in uv],radius=val(r),connect=False)
        self.cmd('sketch.dimension',entities=['c1'],type='diameter',value=2*r)
        self.cmd('sketch.point',point=[-200,-200]);self.cmd('sketch.constraint.fix',entity='p1')
        for coordinate,t in zip(uv,('horizontal','vertical')):
            self.cmd('sketch.dimension',entities=['p1','c1.center'],type=t,value=200+expr(coordinate))
        self.cmd('sketch.solve');self.cmd('sketch.finish')
        self.cmd('solid.extrude',distance=h,name=name,**self._target(body,op))
        return body
    def combine(self,name,target,tools,op='join'):
        self.cmd('solid.combine',target=target,tools=tools,operation=op,keep_tools=False,name=name)
        for t in tools:self.bodies.discard(t)
    def move(self,name,body,translation=None,axis=None,angle=None):
        kwargs={'bodies':body if isinstance(body,list) else [body],'name':name}
        if translation is not None:kwargs['translate']=translation
        if axis is not None:kwargs['axis']=axis;kwargs['angle']=angle
        self.cmd('solid.move',**kwargs)
    def fillet(self,name,body,points,r):
        self.cmd('solid.fillet',edges=[[val(x) for x in p] for p in points],radius=r,name=name)
    def chamfer(self,name,body,points,d):
        self.cmd('solid.chamfer',edges=[[val(x) for x in p] for p in points],distance=d,name=name)
    def rounded_loop_points(self,w,d,r,z):
        k=1/math.sqrt(2)
        return [(0,-d/2,z),(0,d/2,z),(-w/2,0,z),(w/2,0,z)]+[(sx*(w/2-r+r*k),sy*(d/2-r+r*k),z) for sx in (-1,1) for sy in (-1,1)]
    def rounded_box(self,name,w,d,h,r,z,body):
        self.box(name,w,d,h,z=z,body=body,op='new')
        self.fillet(name+'_corners',body,[(sx*w/2,sy*d/2,z+h/2) for sx in (-1,1) for sy in (-1,1)],r)
    def rounded_profile_extrude(self,name,w,d,r,z,height,body,op='join',taper=0):
        self.cmd('sketch.create',plane='XY',offset=z,name=name+'_profile')
        self.cmd('sketch.rectangle.rounded',p0=[-val(w)/2,-val(d)/2],p1=[val(w)/2,val(d)/2],radius=r,connect=False)
        self.cmd('sketch.dimension',entities=['l4','l2'],type='distance',value=w)
        self.cmd('sketch.dimension',entities=['l1','l3'],type='distance',value=d)
        self.cmd('sketch.dimension',entities=['origin','a1.center'],type='horizontal',value=w/2-r)
        self.cmd('sketch.dimension',entities=['origin','a1.center'],type='vertical',value=d/2-r)
        self.cmd('sketch.solve');self.cmd('sketch.finish')
        self.cmd('solid.extrude',distance=height,taper=f'{taper} deg',name=name,**self._target(body,op))
    def slot_cut(self,name,length,width,height,x,y,z,angle,*,body,plane='XY'):
        tool=name+'_tool';self.cmd('sketch.create',plane=plane,name=name+'_profile')
        self.cmd('sketch.draw.dimensioned',command='sketch.slot.overall',params={'p0':[-val(length)/2,0],'p1':[val(length)/2,0],'width':val(width),'connect':False},dimensions={'length':length,'width':width})
        self.cmd('sketch.constraint.horizontal_vertical',points=['origin','a1.center'],mode='horizontal')
        self.cmd('sketch.dimension',entities=['origin','a1.center'],type='horizontal',value=(length-width)/2)
        self.cmd('sketch.constraint.horizontal_vertical',points=['origin','a2.center'],mode='horizontal')
        self.cmd('sketch.solve');self.cmd('sketch.finish')
        self.cmd('solid.extrude',distance=height,name=name+'_tool_extrude',**self._target(tool,'new'))
        self.move(name+'_angle',tool,axis=[0,0,1] if plane=='XY' else [1,0,0],angle=angle)
        self.move(name+'_position',tool,translation=[x,y,z])
        self.combine(name,body,[tool],op='cut')
    def existing_bodies(self):
        with tempfile.TemporaryDirectory(prefix='native-profile-probe-') as tmp:
            path=Path(tmp)/'probe.json';result=Path(tmp)/'result.json'
            path.write_text(json.dumps({'commands':self.commands+[{'command':'document.inspect','params':{'measure':False,'sketches':False}}]}))
            done=subprocess.run(['solidcraft-cli','run',str(path),'--results','--json-out',str(result)],capture_output=True,text=True)
            if done.returncode:raise RuntimeError(done.stderr)
            state=json.loads(result.read_text())[-1]
            return [body['name'] for body in state['bodies']]
    def finish(self,path):
        self.cmd('document.inspect',measure=True,sketches=True)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        Path(path).write_text(json.dumps({'commands':self.commands},indent=2)+'\n')
