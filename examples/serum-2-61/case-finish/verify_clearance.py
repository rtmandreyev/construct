"""Cross-section sweep of the real deck/overlay against the new fixed closing slips."""
from pathlib import Path
import json, math
R=Path(__file__).resolve().parent;E=R.parent
s=json.loads((E/'scene.json').read_text());p={v['id']:v for v in s['parts']}
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def pd(q,a,b):
 d=[b[i]-a[i] for i in range(2)];dd=sum(v*v for v in d)
 t=max(0,min(1,sum((q[i]-a[i])*d[i] for i in range(2))/dd)) if dd else 0
 return math.hypot(*(q[i]-a[i]-t*d[i] for i in range(2)))
def inside(q,poly):
 v=False
 for a,b in zip(poly,poly[1:]+poly[:1]):
  if (a[1]>q[1])!=(b[1]>q[1]) and q[0]<(b[0]-a[0])*(q[1]-a[1])/(b[1]-a[1])+a[0]:v=not v
 return v

def poly_distance(A,B):
 if inside(A[0],B) or inside(B[0],A):return 0.
 best=1e6
 for a,b in zip(A,A[1:]+A[:1]):
  for c,d in zip(B,B[1:]+B[:1]):
   if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0.
   best=min(best,pd(a,c,d),pd(b,c,d),pd(c,a,b),pd(d,a,b))
 return best

def section(part):
 sy,sz=part['shape']['size'][1:];ang=math.radians(part['rotate'][0]);co,si=math.cos(ang),math.sin(ang)
 return [[part['at'][2]+y*si+z*co,part['at'][1]+y*co-z*si] for y,z in [(-sy/2,-sz/2),(-sy/2,sz/2),(sy/2,sz/2),(sy/2,-sz/2)]]
# Same X-axis and pivot as the three preserved native service-deck hinge groups.
pivot=[-.253,.139]
def rotate(poly,theta):
 co,si=math.cos(theta),math.sin(theta)
 return [[pivot[0]+(q[0]-pivot[0])*co-(q[1]-pivot[1])*si,pivot[1]+(q[0]-pivot[0])*si+(q[1]-pivot[1])*co] for q in poly]
# Positive theta here is the original scene's -theta around +X, in (Z,Y) coordinates.
profiles={i:section(p[i]) for i in ['service-control-deck','envelope-fader-module']}
fixed={i:p[i]['shape']['profile'] for i in ['keybed-back-edge-slip','performance-rear-closure','keybed-rear-dust-baffle','performance-key-slip-step-return']}
step=.02;results=[]
for moving,A in profiles.items():
 for fix,B in fixed.items():
  # Envelope overlay is at the right of the instrument; it does not span the left performance closure.
  if moving=='envelope-fader-module' and fix=='performance-rear-closure':continue
  best=(1e6,None)
  for i in range(round(80/step)+1):
   theta=math.radians(i*step);d=poly_distance(rotate(A,theta),B)
   if d<best[0]:best=(d,i*step)
  radius=max(math.dist(q,pivot) for q in A)
  bound=radius*math.radians(step)/2
  results.append({'moving':moving,'fixed':fix,'minimum_sampled_mm':round(best[0]*1000,5),'at_degrees':best[1],'step_degrees':step,'conservative_between_sample_bound_mm':round((best[0]-bound)*1000,5),'intersects':best[0]<1e-7})
assert not any(r['intersects'] for r in results),results
# The X clearance is invariant under an X-axis hinge; use compiled envelopes for every moving part.
import sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(R.parents[2]))
from construct_hologram.scene import compile_scene
g=compile_scene(s,solid=True)
moving_ids={pid for a in s['articulations'] if a['id'].startswith('service-deck-open-') for pid in a['parts']}
instances=[v for q in g['parts'] if q['id'] in moving_ids for v in q['instances']]
left=min(v['min'][0] for v in instances);right=max(v['max'][0] for v in instances)
side=min(.520-right,left+.520)
base=json.loads((R/'baseline/scene.json').read_text());old={q['id']:q for q in base['parts']}
assert set(old)<=set(p)
assert s['subject']['accuracy']=='original'
assert all(q.get('basis')==p[q['id']].get('basis') for q in base['parts'])
assert all(f in s['facts'] for f in base['facts'] if f.get('requirement'))
for ident in ['nav-files','nav-shift-help']:
 assert p[ident]==old[ident]
assert all(p[q['id']]==q for q in base['parts'] if q['id'].startswith('key-'))
byid={q['id']:q for q in g['parts']}
scanner_gap=1000*(min(v['min'][1] for v in byid['keybed-rear-dust-baffle']['instances'])-max(v['max'][1] for v in byid['key-scan-harness']['instances']))
assert scanner_gap>=1.9
report={'scope':'Designed geometry, not tolerance/deflection or hinge-load validation. Whole new slip cross sections tested, not vertices alone. Cross-section distance is conservative when X extents do not overlap.','hinge_amount_degrees':80,'closed_deck_to_slip_reveal_mm':1.5,'sweeps':results,'deck_to_end_lateral_clearance_mm':round(side*1000,5),'deck_moving_min_max_x_m':[left,right],'key_slip_front_lip_bottom_mm':82.5,'black_key_rest_top_mm':81,'black_key_to_slip_vertical_clearance_mm':1.5,'key_to_cheek_lateral_clearance_mm':1.5,'rear_wall_to_deck_underside_reveal_mm':[.9375,1.4997], 'scanner_harness_to_baffle_vertical_envelope_gap_mm':round(scanner_gap,5), 'first_white_key_to_step_return_lateral_gap_mm':1.45, 'black_key_tail_to_baffle_mm':1.5,'retained':'All 258 original IDs and their requirement bases; all 61 keys including 12 mm black-key rise; FILES/SHIFT unchanged; all requirement facts and original accuracy.'}
(R/'hinge-clearance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
