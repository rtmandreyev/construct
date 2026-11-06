"""Render the actual exported GLB through this checkout's Construct Blender add-on."""
import sys, importlib.util, argparse, math, json
from pathlib import Path
sys.dont_write_bytecode=True
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import construct_hologram
name='serum_construct_addon'
spec=importlib.util.spec_from_file_location(name,ROOT/'hosts/blender/construct/__init__.py',submodule_search_locations=[str(ROOT/'hosts/blender/construct')])
addon=importlib.util.module_from_spec(spec)
sys.modules[name]=addon;sys.modules[name+'.construct_hologram']=construct_hologram
spec.loader.exec_module(addon)
a=argparse.ArgumentParser();a.add_argument('--glb',required=True);a.add_argument('--out',required=True);a.add_argument('--samples',type=int,default=64);a.add_argument('--views',default='hero,front-junction,end-right,rear');a.add_argument('--save',action='store_true');a.add_argument('--plain',action='store_true')
args=a.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
root=addon.import_construct(args.glb,wire_scale=.18,metal=1.0)
for k,v in [('build',1.),('open',0.),('metal',1.),('finish',1.)]:root[k]=v
if args.plain:root['finish']=0.
# Idle key motion is disabled in this static dimensional inspection.
for o in bpy.data.objects:
 if o.animation_data and o.animation_data.action and o.animation_data.action.name.startswith('idle'):
  o.animation_data.action=None
root.update_tag();bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
(out/'material-check.json').write_text(json.dumps({m.name:[{'type':n.type,'label':n.label,'value':n.outputs[0].default_value if n.type=='VALUE' else list(n.inputs['Base Color'].default_value), 'transmission':n.inputs['Transmission Weight'].default_value if n.type=='BSDF_PRINCIPLED' else None, 'alpha':n.inputs['Alpha'].default_value if n.type=='BSDF_PRINCIPLED' else None} for n in m.node_tree.nodes if n.type in ['VALUE','BSDF_PRINCIPLED']] for m in bpy.data.materials if m.use_nodes and any(k in m.name for k in ['key polymer','ivory','display','cap','glass'])},indent=2))
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=args.samples;scene.cycles.use_denoising=True
scene.cycles.max_bounces=12;scene.cycles.transmission_bounces=8;scene.cycles.transparent_max_bounces=12
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.exposure=0;scene.view_settings.gamma=1;scene.use_nodes=False
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
scene.world.color=(.18,.18,.18);scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.32,.36,.42,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25
# Neutral studio light, no coloured lights or hidden geometry masking the seams.
def area(name,loc,power,size,target):
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
 ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();return ob
area('Softbox key',(-.65,-.65,1.7),35,1.5,(0,0,.07))
area('Softbox fill',(1.0,-.15,.8),18,1.0,(0,0,.07))
area('Rear edge',(-.15,.9,1),0,.9,(0,0,.08))
rear_fill=area('Rear seam inspection fill',(0,1.0,.65),45,1.0,(0,.22,.085));rear_fill.hide_render=True
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));ground=bpy.context.object;ground.name='Studio floor (render only)'
m=bpy.data.materials.new('Studio floor');m.diffuse_color=(.105,.12,.14,1);m.use_nodes=True;m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=m.diffuse_color;m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.76;ground.data.materials.append(m)
camdata=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',camdata);scene.collection.objects.link(cam);scene.camera=cam
views={
 'hero':((-.95,-1.3,1.1),(0,0,.075),1.3,(1600,1000)),
 'front-junction':((.12,-.65,.19),(.05,-.065,.086),.88,(1600,800)),
 'end-right':((1.0,-.4,.29),(.475,-.005,.078),.47,(1300,1000)),
 'end-left':((-.98,-.4,.26),(-.465,-.005,.08),.48,(1300,1000)),
 'rear':((0,1.25,.27),(0,.244,.085),1.16,(1600,650)),
 'front-low':((.05,-1.4,.13),(0,-.12,.065),1.16,(1600,650)),
 'editor':((.13,-.85,.75),(.13,.1923,.138),.30,(1100,800)),
 'hero-left':((-.95,-1.3,1.1),(0,0,.075),1.3,(1600,1000)),
 'service':((.95,-1.3,1.2),(0,0,.13),1.4,(1600,1000)),
}
for name in args.views.split(','):
 loc,target,scale,res=views[name]
 rear_fill.hide_render=name not in ['rear','service']
 root['open']=1. if name=='service' else 0.;root.update_tag();bpy.context.view_layer.update()
 cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=scale
 scene.render.resolution_x,scene.render.resolution_y=res;scene.render.resolution_percentage=100
 scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
root['open']=0.;root.update_tag();bpy.context.view_layer.update()
rear_fill.hide_render=True
if args.save:
 loc,target,scale,res=views['hero'];cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();camdata.ortho_scale=scale;scene.render.resolution_x,scene.render.resolution_y=res
 bpy.ops.object.select_all(action='DESELECT');root.select_set(True);bpy.context.view_layer.objects.active=root
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'serum61-finished.blend'))
(out/'render-info.json').write_text(json.dumps({'imported_glb':str(Path(args.glb).resolve()),'engine':'CYCLES','samples':args.samples,'views':args.views.split(','),'native_addon':str(ROOT/'hosts/blender/construct/__init__.py'),'geometry_edits_in_blender':False,'root_properties':{k:root[k] for k in ['build','open','metal','finish']}},indent=2))
