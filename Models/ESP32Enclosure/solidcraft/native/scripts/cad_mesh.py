"""Mesh the native CAD, with an explicit blind-side-bore export workaround.

Only the four modeled mounting bores are retessellated from CAD entry circles,
complete native blind caps and evaluated native radius/depth. Other surfaces use
OCCT triangulation unchanged. Open or inconsistent results are rejected.
"""
import json
from pathlib import Path
import numpy as np
import trimesh
LINEAR=.02

def export_print_mesh(parts,path,parameters=None):
 scene=trimesh.Scene();report={'status':'passed','units':'mm','linear_deflection_mm':LINEAR,'angular_deflection_rad':.1,'parts':{}}
 for name,shape in parts.items():
  if name in ('body','button_fit_frame') and parameters:
   from bore_mesh import mounting_bore_mesh
   mesh,recoveries=mounting_bore_mesh(shape,parameters,LINEAR)
  else:
   vertices,triangles=shape.tessellate(LINEAR,.1)
   mesh=trimesh.Trimesh(vertices=[list(v) for v in vertices],faces=triangles,process=True);recoveries=[]
  if not mesh.is_volume or not mesh.is_watertight or not mesh.is_winding_consistent:raise AssertionError('CAD mesh is not a closed positive volume: '+name)
  if len(mesh.split(only_watertight=False))!=1:raise AssertionError('Expected one connected print mesh: '+name)
  import manifold3d
  checked=manifold3d.Manifold(manifold3d.Mesh(vert_properties=np.asarray(mesh.vertices,dtype=np.float32),tri_verts=np.asarray(mesh.faces,dtype=np.uint32)))
  if checked.status()!=manifold3d.Error.NoError:raise AssertionError('Manifold rejected print mesh: '+name)
  mesh.units='mm';scene.add_geometry(mesh,node_name=name,geom_name=name)
  report['parts'][name]={'watertight':True,'winding_consistent':True,'manifold_check':'passed','connected_bodies':1,'cad_surface_tessellation_recoveries':recoveries}
 scene.units='mm';Path(path).write_bytes(scene.export(file_type='3mf'))
 Path(path).with_name(Path(path).stem+'-mesh-report.json').write_text(json.dumps(report,indent=2)+'\n')
 return report
