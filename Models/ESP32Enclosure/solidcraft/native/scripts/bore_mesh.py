"""Retessellate the four explicitly modeled blind side-mounting bores.

This avoids SolidCraft STEP trim defects on those cylinders. The native evaluated
radius/depth, CAD cylindrical faces and complete planar blind caps must agree.
No other opening is closed, and the CAD/STEP geometry is never changed.
"""
import math
import numpy as np
import trimesh
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder,GeomAbs_Plane,GeomAbs_BSplineSurface
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location

def mounting_bore_mesh(shape,parameters,linear=.02):
 radius=parameters['button_insert_pilot_diameter']/2;depth=parameters['button_insert_bore_depth'];faces=list(shape.faces());groups={}
 for index,face in enumerate(faces):
  a=BRepAdaptor_Surface(face.wrapped)
  if a.GetType()!=GeomAbs_Cylinder:continue
  c=a.Cylinder();axis=c.Axis().Direction();origin=c.Location()
  if abs(c.Radius()-radius)>1e-6 or abs(abs(axis.X())-1)>1e-8 or abs(origin.Z()-5)>1e-5:continue
  key=(round(origin.Y(),6),round(origin.Z(),6));g=groups.setdefault(key,{'center':np.array([0.,origin.Y(),origin.Z()]),'sides':[],'caps':[],'x':[],'surface_error':0.})
  g['sides'].append(index);g['x'].extend(v.X for v in face.vertices())
 if len(groups)!=4:raise AssertionError('Expected the four native blind mounting bores')
 excluded=set()
 for g in groups.values():
  g['entry']=min(g['x']);g['end']=max(g['x'])
  if abs(g['end']-g['entry']-depth)>2e-5:raise AssertionError('Native bore side extent differs from its driving depth')
  for index,face in enumerate(faces):
   a=BRepAdaptor_Surface(face.wrapped)
   if a.GetType()!=GeomAbs_Plane or abs(abs(a.Plane().Axis().Direction().X())-1)>1e-8:continue
   points=np.array([list(v.center()) for v in face.vertices()])
   if not len(points) or np.max(np.abs(points[:,0]-g['end']))>2e-5:continue
   if np.max(np.linalg.norm(points[:,1:]-g['center'][1:],axis=1))>radius+2e-5:continue
   g['caps'].append(index)
  cap_area=sum(faces[i].area for i in g['caps'])
  if abs(cap_area-math.pi*radius**2)>1e-3:raise AssertionError('Bore does not have its complete native planar blind cap')
  # The exporter can represent a fragment of the same bore as a B-spline.
  # Recognize it by its entire sampled surface and the evaluated cutter domain.
  for index,face in enumerate(faces):
   a=BRepAdaptor_Surface(face.wrapped)
   if a.GetType()!=GeomAbs_BSplineSurface:continue
   points=np.array([a.Value(u,v).Coord() for u in np.linspace(a.FirstUParameter(),a.LastUParameter(),5) for v in np.linspace(a.FirstVParameter(),a.LastVParameter(),5)])
   error=float(np.max(np.abs(np.linalg.norm(points[:,1:]-g['center'][1:],axis=1)-radius)))
   if error<=linear/2 and points[:,0].min()>=g['entry']-1e-4 and points[:,0].max()<=g['end']+1e-4:
    g['sides'].append(index);g['surface_error']=max(g['surface_error'],error)
  excluded.update(g['sides']+g['caps'])
 shape.mesh(linear,.1);vertices=[];triangles=[]
 for index,face in enumerate(faces):
  if index in excluded:continue
  loc=TopLoc_Location();poly=BRep_Tool.Triangulation_s(face.wrapped,loc)
  if poly is None:raise AssertionError('A non-bore CAD face failed triangulation')
  transform=loc.Transformation();offset=len(vertices)
  for i in range(1,poly.NbNodes()+1):
   p=poly.Node(i).Transformed(transform);vertices.append([p.X(),p.Y(),p.Z()])
  reverse=face.wrapped.Orientation()==TopAbs_REVERSED
  for triangle in poly.Triangles():
   a,b,c=(triangle.Value(i)+offset-1 for i in (1,2,3));triangles.append([a,c,b] if reverse else [a,b,c])
 mesh=trimesh.Trimesh(vertices=vertices,faces=triangles,process=True)
 if not mesh.is_winding_consistent:raise AssertionError('Non-bore CAD mesh winding is inconsistent')
 counts=np.bincount(mesh.edges_unique_inverse,minlength=len(mesh.edges_unique))
 if np.any(counts>2):raise AssertionError('Non-bore CAD mesh has non-manifold edges')
 boundary=mesh.edges[counts[mesh.edges_unique_inverse]==1][:,::-1];following={int(a):int(b) for a,b in boundary}
 if len(following)!=len(boundary) or set(following)!=set(following.values()):raise AssertionError('Branched bore entry boundary')
 loops=[]
 while following:
  first=next(iter(following));loop=[first];current=following.pop(first)
  while current!=first:loop.append(current);current=following.pop(current)
  loops.append(loop)
 if len(loops)!=4:raise AssertionError('Only the four entry circles may remain open')
 vertices=mesh.vertices.tolist();triangles=mesh.faces.tolist();report=[];used=set()
 for loop in loops:
  points=np.asarray([vertices[i] for i in loop]);candidates=[]
  for key,g in groups.items():
   radial=points[:,1:]-g['center'][1:];error=max(float(np.max(np.abs(points[:,0]-g['entry']))),float(np.max(np.abs(np.linalg.norm(radial,axis=1)-radius))))
   if error<=.001:candidates.append((error,key,g))
  if len(candidates)!=1:raise AssertionError('Entry loop must match exactly one native mounting bore')
  error,key,g=candidates[0]
  if key in used:raise AssertionError('Repeated native bore entry')
  used.add(key)
  for index in loop:
   p=np.asarray(vertices[index]);radial=p[1:]-g['center'][1:];p[0]=g['entry'];p[1:]=g['center'][1:]+radius*radial/np.linalg.norm(radial);vertices[index]=p.tolist()
  # Refine coarse boundary arcs and their one existing planar entry triangle.
  refinements=0
  while True:
   chosen=None
   for k,a in enumerate(loop):
    b=loop[(k+1)%len(loop)];ra=np.asarray(vertices[a])[1:]-g['center'][1:];rb=np.asarray(vertices[b])[1:]-g['center'][1:]
    sag=radius*(1-math.sqrt(max(0.,(1+np.clip(np.dot(ra,rb)/radius**2,-1,1))/2)))
    if sag>linear:chosen=(k,a,b,ra,rb);break
   if chosen is None:break
   k,a,b,ra,rb=chosen;radial=ra+rb
   if np.linalg.norm(radial)<1e-8:raise AssertionError('Bore boundary spans a half turn')
   point=[g['entry'],*(g['center'][1:]+radius*radial/np.linalg.norm(radial))];middle=len(vertices);vertices.append(point)
   incident=[i for i,t in enumerate(triangles) if a in t and b in t]
   if len(incident)!=1:raise AssertionError('Entry refinement needs exactly one planar neighbor')
   i=incident[0];tri=triangles[i]
   for j in range(3):
    u,v,w=tri[j],tri[(j+1)%3],tri[(j+2)%3]
    if {u,v}=={a,b}:break
   triangles[i]=[u,middle,w];triangles.append([middle,v,w]);loop.insert(k+1,middle);refinements+=1
   if refinements>256:raise AssertionError('Excessive entry refinement')
  end=[]
  for index in loop:
   point=list(vertices[index]);point[0]=g['end'];end.append(len(vertices));vertices.append(point)
  center=len(vertices);vertices.append([g['end'],*g['center'][1:]])
  for i,a in enumerate(loop):
   j=(i+1)%len(loop);b=loop[j];c=end[j];d=end[i]
   triangles.extend(([a,b,c],[a,c,d],[center,d,c]))
  report.append({'surface':'native blind mounting-bore cutter','radius_mm':radius,'depth_mm':depth,'entry_x_mm':g['entry'],'center_yz_mm':g['center'][1:].tolist(),'native_cylindrical_faces_replaced':len(g['sides']),'native_cap_faces_replaced':len(g['caps']),'ring_vertices':len(loop),'entry_edges_refined':refinements,'maximum_entry_projection_mm':error,'maximum_native_approximated_surface_radial_error_mm':g['surface_error']})
 result=trimesh.Trimesh(vertices=vertices,faces=triangles,process=False)
 if not result.is_volume or not result.is_watertight or not result.is_winding_consistent:raise AssertionError('Native bore retessellation must produce a closed positive mesh')
 return result,report
