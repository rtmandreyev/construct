"""Focused, repeatable revision from the frozen audited example baseline, not the original run."""
from pathlib import Path
import json, math, copy
R=Path(__file__).resolve().parent; E=R.parent
old=json.loads((R/'baseline/scene.json').read_text());s=copy.deepcopy(old)
parts={p['id']:p for p in s['parts']};new=[]
c=math.cos(math.radians(8));sn=math.sin(math.radians(8));normal=[0,c,sn]
def shift(p,amount): return [p[i]+normal[i]*amount for i in range(3)]
def add(pid,label,shape,at=(0,0,0),stage=2,basis=('request.standalone',),role='structure',rotate=None):
 p={'id':pid,'label':label,'shape':shape,'at':list(at),'role':role,'stage':stage,'certainty':'inferred','source':'design','basis':list(basis),'look':{'fill':'dark','weight':.55,'alpha':.78}}
 if rotate:p['rotate']=rotate
 s['parts'].append(p);new.append(pid);return p

def profile(pid,label,pts,x,width,basis=('request.standalone',)):
 return add(pid,label,{'type':'extrude','axis':'x','profile':pts,'height':width},(x,0,0),basis=basis)
# A 1 mm lateral reveal to the unchanged 1038 mm deck. Preserve the faceted side profile,
# outer 1080 mm width and corner taper, while making the inside edge continuous.
for sign,side in [(-1,'left'),(1,'right')]:
 p=parts['end-structure-'+side];p['at'][0]=sign*.530
 p['shape']['sections']=[[-.260,.006,.018,.130],[-.258,.010,.01747,.132],[-.245,.010,.014,.145],[.048,.010,.014,.101],[.245,.010,.017,.064],[.258,.010,.02307,.0588],[.260,.006,.024,.058]]
# Extend the existing rear wall up to a 1 mm reveal below the inclined deck's underside.
rear_top=.119-math.tan(math.radians(8))*(-.245+.105)-.0015/c-.0009375
p=parts['rear-io-carrier'];p['shape']['size'][1]=rear_top-.017;p['at'][1]=(.017+rear_top)/2
# These two overlays overhung the enclosing deck. All controls and their positions stay put.
parts['filter-2-module']['shape']['size'][0]=.119
parts['envelope-fader-module']['shape']['size'][2]=.088
parts['performance-control-plinth']['shape']['size'][0]=.162
# Keep the harness entirely inside the newly closed rear wall and below the closed deck.
p=parts['hinge-service-loop'];p['shape']['path'][-3:]=[[.12,.095,-.230],[.108,.115,-.232],[.12,.126,-.228]]
# The minimum closed plan gap is 1.5 mm from the deck's most forward underside corner.
front_z=-.105+.1525*c+.0015*sn
back=front_z+.0015
roof=lambda z:.119-math.tan(math.radians(8))*(z+.105)+.0015/c
zt=.087;thick=.003
profile('keybed-back-edge-slip','Fixed full-keybed back-edge slip; 1.5 mm closing reveal',[
 [back,roof(back)],[zt,roof(zt)],[zt,.0825],[zt-.003,.0825],[zt-.003,roof(zt)-thick],[back,roof(back)-thick]],-.351,.870,('request.keys','request.standalone'))
# A return behind the key backs blocks the electronics even between white keys. It ends
# 1.5 mm behind the black-key tails, embeds 0.5 mm into the action frame, and leaves the
# existing scanner harness below its 54.5 mm lower edge (1 mm cable clearance).
profile('keybed-rear-dust-baffle','Opaque keybed rear return below slip; keeps electronics out of the key opening',[
 [.075,.0545],[.0765,.0545],[.0765,roof(.0765)-thick],[.075,roof(.075)-thick]],-.351,.870,('request.keys','request.standalone'))
# Shorter front edge on the performance side leaves OCT-/OCT+/HOLD completely exposed.
pz=.069
profile('performance-rear-closure','Fixed performance-side continuation of key slip; clears octave/hold controls',[
 [back,roof(back)],[pz,roof(pz)],[pz,.0715],[pz-.003,.0715],[pz-.003,roof(pz)-thick],[back,roof(back)-thick]],-.519,.167)
# Close the exposed side of the stepped performance/key-slip transition. This fixed
# end return joins the two folds and the left cheek; its lower edge seats on the frame.
profile('performance-key-slip-step-return','Fixed end return closes stepped performance-to-key-slip corner',[
 [.068,.0545],[.087,.0545],[.087,.0825],[.084,.0825],[.084,roof(.087)-thick],[.068,roof(.068)-thick]],-.357,.006,('request.keys','request.standalone'))
# Fixed cheek rails mask the action frame at either side. The 1.5 mm key clearance is an
# intentional key opening. Thin downward returns close the outside, without filling the bay.
cheek_profile=[[.087,.0825],[.094,.0825],[.109,.0735],[.244,.0705],[.244,.0545],[.087,.0545]]
profile('keybed-cheek-right','Right key cheek; 1.5 mm lateral key clearance',cheek_profile,.49705,.02195,('request.keys',))
profile('keybed-cheek-left','Left key cheek between action and performance plinth',cheek_profile,-.356,.00495,('request.keys',))
add('keybed-cheek-right-lower-return','Right cheek lower return to tray',{'type':'box','size':[.0015,.0375,.157]},(.51825,.03575,.1655),basis=('request.keys','request.standalone'))
add('performance-plinth-outer-return','Outer return closes plinth to base tray',{'type':'box','size':[.0025,.0265,.194]},(-.51775,.03025,.147))
add('performance-plinth-keyside-return','Inner plinth return closes its key-side face',{'type':'box','size':[.0015,.0265,.194]},(-.35775,.03025,.147))
add('key-slip-end-mounts','Hidden end cleats fasten fixed slip to end castings',{'type':'box','size':[.005,.006,.020]},(-.5195,.092,.059),basis=('request.keys','request.standalone'))['repeat']={'count':2,'step':{'at':[1.039,0,0]}}
# Keep each existing optical display module's ID, aperture and geometry. Its opaque black
# optical face receives actual pixel surfaces, with a separate thin clear cover above them.
# A layer stack is necessary: transparent glass alone showed the metal bezel behind it.
glass_ids=[p['id'] for p in old['parts'] if p['id'].endswith('glass')]
for pid in glass_ids:
 orig=parts[pid];width,_,depth=orig['shape']['size']
 q=add(pid.replace('-glass','-cover-glass'),'Clear optical cover above '+orig['label'],{'type':'box','size':[width,.0008,depth]},shift(orig['at'],.0025),4,tuple(orig.get('basis',['request.standalone'])),'identity',[8,0,0])
 for art in s['articulations']:
  if pid in art['parts']:art['parts'].append(q['id']);break
# The exporter maps surface finishes, not raw line primitives. These optical pixel/LED
# surfaces follow the existing graph and assignment traces, so the GLB carries their colours too.
trace=parts['display-native-waveform-and-modulation-traces']['shape']['paths']
for index in list(range(4))+list(range(8,19))+[24,25]:
 path=copy.deepcopy(trace[index])
 if index<4:
  gid=glass_ids[index] if index<3 else 'central-7inch-editor-glass'
  oldglass=next(p for p in old['parts'] if p['id']==gid)
  # Offset the old curve to the pixel plane too; no change to the screen's waveform or graph.
  def pixel(p):
   dn=sum((p[i]-oldglass['at'][i])*normal[i] for i in range(3))
   return [p[i]+normal[i]*(.0017-dn) for i in range(3)]
  path=[pixel(p) for p in path];trace[index]=[shift(p,-.0001) for p in path];radius=.0001
  pid=('osc-'+chr(97+index)+'-waveform-pixels') if index<3 else 'central-modulation-graph-pixels'
  basis=('serum.R02',) if index<3 else ('serum.R21','serum.R25')
 else:
  path=[shift(p,.0003) for p in path];radius=.00028
  pid={8:'osc-a-position-modulation-lightguide',9:'filter-1-cutoff-modulation-lightguide',10:'modulation-depth-lightguide',24:'selected-source-bank-lightguide',25:'selected-source-pad-lightguide'}.get(index,'macro-'+str(index-10)+'-value-lightguide')
  basis=('serum.R22','serum.R25')
 # Keep at most 49 points per tube; existing arcs/graphs keep the same shape.
 if len(path)>64:path=path[::2]
 q=add(pid,'Functional graph/assignment light: '+pid,{'type':'tube','path':path,'radius':radius,'sides':6,'samples':1,'smooth':False,'caps':True},stage=6,basis=basis,role='data')
 for art in s['articulations']:
  if 'display-native-waveform-and-modulation-traces' in art['parts']:art['parts'].append(q['id']);break
# Existing illuminated ON and selected-source buttons get functional backlit polymer finishes.
# No logo, brand badge, new controls or decorative RGB strips are added.
for f in s['facts']:
 if f['key']=='revision':f['value']+=' Second revision: case closing slip/returns, deliberate reveals and interface-sourced export finishes; original requirement links retained. Self-reviewed in solid and Cycles.'
# Keep the toolkit's 64-part articulation lists bounded without changing any existing joint.
new_display_parts=[]
for art in s['articulations']:
 attached=[pid for pid in art['parts'] if pid in new]
 new_display_parts.extend(attached)
 art['parts']=[pid for pid in art['parts'] if pid not in new]
if new_display_parts:
 art=copy.deepcopy(next(a for a in s['articulations'] if a['id']=='service-deck-open-0'))
 art['id']='service-deck-open-3';art['parts']=new_display_parts;s['articulations'].append(art)
s['presentation']['views'].extend([
 {'id':'case-low-front','label':'Closed case / low front inspection','yaw':0,'pitch':10,'distance':.86,'target':'keybed-back-edge-slip'},
 {'id':'case-right-end','label':'Closed case / end and deck reveals','yaw':65,'pitch':16,'distance':1.25,'target':'end-structure-right'}
])
s['authoring']['outcome']='self-reviewed'
(E/'scene.json').write_text(json.dumps(s,indent=1)+'\n')

# The sampled RGBs come from the UI itself, not the manual's green callouts or red outlines.
# Finishes and assignment of that palette to a physical object are new design choices.
M=[]
def mat(parts,name,color,finish,**kw):M.append(dict(parts=parts,name=name,color=color,finish=finish,**kw))
mat(['native-compute-carrier','native-cpu-module','ram-*','nvme-*','audio-dma-interface-controller','clock-dac-adc-analog-board','key-scanner-pressure-controller','midi-usb-pedal-io-board','headphone-amp-and-level-board','panel-scan-display-electronics'],'Designed electronics packaging / soldermask','#23433D','plastic',roughness=.65)
mat(['key-*-black'],'Near-black satin key polymer / UI key shadows pp16,37','#151719','plastic',roughness=.4)
mat(['key-*-c*','key-*-d*','key-*-e*','key-*-f*','key-*-g*','key-*-a*','key-*-b*'],'Cool ivory molded key polymer / adapted from UI keys pp16,37','#D9E1E6','plastic',roughness=.32)
mat(['*-waveform-pixels'],'Lime wavetable pixels / p37 waveform','#80CB4A','light',emissive='#406E1E')
mat(['*graph-pixels','*lightguide'],'Cyan modulation and selection lightguides / p188 LFO','#0FADF6','light',emissive='#064E7A')
mat(['osc-*-on'],'Enabled oscillator backlit polymer / p37 green enable LED','#30402D','plastic',roughness=.65,emissive='#315F18')
mat(['source-family-lfo','source-or-slot-2','mod-assign'],'Selected modulation controls / p188 cyan','#23343F','plastic',roughness=.65,emissive='#082A3D')
mat(['*-cover-glass'],'Clear low-reflection cover glass / designed optical finish','#DDE5EA','glass',roughness=.13)
mat(['*glass','central-editor-frame'],'Opaque black bonded display optical face / pp16,37,188 graph background','#181D20','plastic',metallic=0.,roughness=.72)
mat(['*feet','*ribbon','performance-*-wheel'],'Soft-touch charcoal elastomer / UI dark control surrounds pp16,37','#1B1E23','rubber',roughness=.82)
mat(['osc-*-pitch','osc-*-position','osc-*-warp?','osc-*-unison','osc-*-detune','osc-*-pan','osc-*-level','filter-*-cutoff','filter-*-resonance','filter-*-drive','filter-*-var','filter-*-pan','filter-*-mix','editor-e?','macro-?','browse-data-navigator','modulation-signed-amount','main-output-volume','headphone-level'],'Graphite soft-touch encoder caps / p37 knob faces','#404952','rubber',roughness=.62)
mat(['editor-softkey-*','page-*','nav-*','source-family-*','source-or-slot-*','mod-*','osc-*-type','osc-*-edit','osc-*-route','filter-*-on','filter-*-route','performance-octave-*','performance-hold','env-*-fader','hard-power-rocker'],'Charcoal molded control keys / pp16,37 dark tiles','#1B1E23','plastic',roughness=.65)
mat(['osc-*-module','filter-*-module','envelope-fader-module'],'Blue-grey matte anodized synthesis panels / pp16,37','#8093A2','brushed',metallic=.7,roughness=.6)
mat(['end-structure-*','keybed-back-edge-slip','performance-rear-closure','performance-key-slip-step-return','keybed-cheek-*','keybed-rear-dust-baffle'],'Bead-blasted charcoal anodized perimeter / pp16,37 frame','#1B1E23','brushed',metallic=.72,roughness=.63)
mat(['service-control-deck'],'Blue-grey anodized main deck / p37 panel controls','#6A7A87','brushed',metallic=.68,roughness=.57)
mat(['envelope-fader-slots'],'Black fader track recesses / UI dark wells','#13171A','plastic',roughness=.9)
mat(['io-*-jacks','midi-*-din','pedal-*-jack','pedal-expression*','headphone-output-socket','usb-*','rear-service-hinge-barrel','hinge-bracket-pair'],'Satin nickel connector and hinge hardware / designed finish','#8D989F','chrome',roughness=.3)
mat(['*'],'Charcoal anodized chassis / pp16,37 upper surround','#1B1E23','brushed',metallic=.7,roughness=.58)
palette=[
 {'sample':'#1B1E23','page':37,'image':'first embedded UI screenshot, 1190x740','crop_xyxy':[180,4,220,15],'feature':'upper dark tile, modal RGB; used for chassis and perimeter'},
 {'sample':'#181D20','page':37,'crop_xyxy':[405,437,475,540],'feature':'envelope graph background, modal RGB; opaque LCD wells'},
 {'sample':'#8093A2','page':37,'crop_xyxy':[220,270,252,325],'feature':'blue-grey control-panel gradient; one of the two dominant samples'},
 {'sample':'#6A7A87','pages':[16,37],'feature':'dominant darker blue-grey control panel RGB in embedded screenshots; main deck'},
 {'sample':'#95ACBC','page':37,'crop_xyxy':[137,72,306,90],'feature':'pale blue-grey oscillator header reference; recorded reference, not a large painted accent'},
 {'sample':'#404952','page':37,'crop_xyxy':[96,284,106,296],'feature':'knob face, modal RGB; soft-touch cap tone'},
 {'sample':'#80CB4A','page':37,'crop_xyxy':[76,140,335,240],'feature':'actual lime waveform stroke, bright pixel cluster; not the red explanatory border'},
 {'sample':'#5DDC33','page':37,'crop_xyxy':[82,78,91,87],'feature':'oscillator enable indicator reference; adapted/dimmed for backlit ON switches'},
 {'sample':'#0FADF6','pages':[37,188],'crop_xyxy':[630,426,986,562],'feature':'cyan LFO stroke, bright pixel cluster; modulation/selection guides'},
 {'sample':'#D9E1E6 / #151719','pages':[16,37],'feature':'designed physical cool-ivory/near-black key pair, adapted from UI keyboard light/shadow; not a literal calibrated sample'}]
mapdoc={'materials':M,'palette_provenance':{'source':'Official Serum 2 User Guide, manual 1.0.3, public PDF byte-identical to the supplied copy','source_ref':'https://xferrecords.com/manual/serum-2/docs','sampling':'RGB from extracted embedded screenshot images, not rendered-page whitespace or manual annotations. Screenshots are not calibrated material measurements. Pages are printed/PDF page numbers. Hardware assignment, finish and brightness are designed.','samples':palette,'physical_finishes':'Matte anodized blue-grey deck, bead-blasted charcoal perimeter, soft-touch graphite controls, molded polymer keys, thin clear cover glass over opaque black display modules, emissive functional pixels/lightguides. Construct retains its own palette; no colours were added to scene.json.'}}
(E/'materials.json').write_text(json.dumps(mapdoc,indent=2)+'\n')
changed={p['id']:[k for k in p if p.get(k)!=next(q for q in old['parts'] if q['id']==p['id']).get(k)] for p in s['parts'] if p['id'] in {q['id'] for q in old['parts']} and p!=next(q for q in old['parts'] if q['id']==p['id'])}
(R/'part-change-log.json').write_text(json.dumps({'added':new,'changed':changed,'removed':[],'new_count':len(s['parts']),'rear_top_m':rear_top,'key_slip_rear_z_m':back,'closed_deck_reveal_m':.0015},indent=2)+'\n')
assert s['subject']['accuracy']=='original'
assert all(f in s['facts'] for f in old['facts'] if f.get('requirement'))
assert all(p.get('basis')==next(q for q in old['parts'] if q['id']==p['id']).get('basis') for p in s['parts'] if p['id'] in {q['id'] for q in old['parts']})
print('Kept all',len(old['parts']),'existing IDs and bases;',len(new),'new semantic parts;',len(changed),'existing parts adjusted')
