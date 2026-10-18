"""Create an explicit, reviewable WA SRFF crosswalk from profiled labels.
Unrecognized labels deliberately remain unresolved. Not a fuzzy classifier.
"""
import csv,json
from pathlib import Path
P=(Path(__file__).resolve().parents[2] / 'Unified_MMUCC6')
profile=json.loads((P/'qa/source_comparison_WA_2026-10-15/srff_profile.json').read_text())
fixed='Fence|Tree or Stump (stationary)|Fire Hydrant|Earth Bank or Ledge|Building|Metal Sign Post|Concrete Barrier/Jersey Barrier - Face|Linear Curb|Over Embankment - No Guardrail Present|Boulder (stationary)|Roadway Ditch|Mailbox|Wood Sign Post|Utility Box|Rock Bank or Ledge|Guardrail - Face|Railway Signal Pole|Culvert and/or other Appurtenance in Ditch|Utility Pole|Guardrail - Leading End|All Other Fixed Objects (On the Road)|Bridge Rail - Face|Underside of Bridge|Street Light Pole or Base|Retaining Wall (concrete, rock, brick, etc.)|Over Roadway Power Lines|Signal Pole|Railway Crossing Gate|Guardrail - Through, Over or Under|Cable Barrier|Concrete Barrier/Jersey Barrier - Through, Over or Under|Guide Post|Crash Cushions - Impact Attenuators|Snow Bank|Concrete Barrier/Jersey Barrier - Leading End|Over Roadway Branches|Railroad Tracks (ie. Run off the road and hit the tracks|Bridge Rail - Leading End|Bridge Column, Pier or Pillar|Toll Booth|Drawbridge Crossing Gate Arm|Bridge Abutment|Tunnel Wall / Barrier within Tunnel|Bridge Rail - Through, Over or Under|Reversible Lane Control Gate|Parking Meter|Expansion Joint or Similar (On the Road)|Manhole/Utilities/Drain Grates (Fixed)|Closed Toll Gate|Overhead Sign Support'.split('|')
nonfixed='Strikes or Was Struck by Object from the Load of Another Vehicle|Miscellaneous Object or Debris on Road|Strikes or Was Struck by a Part of Another Vehicle (Not from Load)|Fallen rock hit by vehicle (on the road)|Fallen tree hit by vehicle (on the road)|Garbage / Recycle Containers (Out for PU)|Temporary Traffic Sign, Barricade or Construction Materi|Temporary Traffic Sign or Construction Materials|Tire Tread|Falling rock on vehicle (on the road)|Manhole/Utilities/Drain Cover (Not Secure/Loose)|Falling tree on vehicle (on the road)|Vehicle hits Snowslide (on the road)|Vehicle hits Mud or Landslide (on the road)|Debris from Previous Collision|Mud or Landslide strikes vehicle (on the road)'.split('|')
animals='Domestic animal (horse, cow, sheep, etc)|Vehicle Strikes All Other Non-Domestic Animal|Vehicle Strikes Deer|Non Domestic Animal Struck Again|Domestic animal other (cat, dog, etc)|Vehicle Strikes Elk|Domestic Animal (ridden)|Domestic Animal Struck Again'.split('|')
rows=[]
def add(group,label,value='',manner='',note='Exact source label crosswalk'):
    rows.append(dict(source_field=group,source_label=label,canonical_value=value,manner_code=manner,note=note,status='REVIEWED' if value or manner else 'UNRESOLVED'))
for lab in profile['FIRST COLLISION TYPE / OBJECT STRUCK']:
    lo=lab.lower();g='';m='';note='First collision event; no inference from later events'
    if lo.startswith(('from same direction','from opposite direction','same direction')) or lab in ['Entering at angle','All Other Multi Vehicle']:
        g='MOTOR_VEHICLE_IN_TRANSPORT'
        if 'rear-end' in lo or 'rear end' in lo:m='1'
        elif 'head-on' in lo:m='2'
        elif 'sideswipe' in lo:m='8' if lo.startswith('from opposite') else '7'
        elif lab=='Entering at angle' or ('turn' in lo and ('one straight' in lo or 'one right turn' in lo)):m='6'
        else:note='Motor vehicle collision known; impact geometry unspecified, so C09 remains blank'
    elif lab=='One parked--one moving':g='PARKED_VEHICLE';m='0'
    elif lab in ['One car leaving parked position','One car entering parked position']:
        g='MOTOR_VEHICLE_IN_TRANSPORT';note='Parking maneuver does not establish impact geometry'
    elif lab=='Trailer Parked (Legally or Not)':g='PARKED_VEHICLE';m='0'
    elif lab in animals:g='ANIMAL';m='0'
    elif lab in fixed:g='FIXED_OBJECT';m='0'
    elif lab in nonfixed:g='OTHER_NON_FIXED_OBJECT';m='0'
    elif lab in ['Vehicle Strikes Pedalcyclist','Pedalcyclist Strikes Moving Vehicle']:g='PEDALCYCLIST';m='0'
    elif lab in ['Vehicle going straight hits pedestrian','Vehicle turning right hits pedestrian','Vehicle turning left hits pedestrian','Vehicle hits Pedestrian - All Other Actions','Vehicle backing hits pedestrian','Pedestrian Struck Again']:g='PEDESTRIAN';m='0'
    elif lab in ['Vehicle Strikes Railway Vehicle','Railway Vehicle Strikes Vehicle']:g='TRAIN';m='0'
    elif lab=='Vehicle overturned':g='ROLLOVER_OVERTURN';m='0'
    elif lab=='Jackknife Trailer':g='JACKKNIFE';m='0'
    elif lab=='Fire started in vehicle':g='FIRE_EXPLOSION';m='0'
    elif lab=='Into River, Lake, Swamp, etc.':g='IMMERSION';m='0'
    elif lab in ['Breakage of any part of the vehicle resulting in injury or in further property damage','Person fell, jumped or was pushed from vehicle','All other non-collision']:g='OTHER_NON_COLLISION';m='0'
    else:note='Unknown, ambiguous or non-motor-vehicle pairing; preserve raw label without inventing a partner or C09'
    add('FIRST COLLISION TYPE / OBJECT STRUCK',lab,g,m,note)
maps={
 'MOST SEVERE INJURY TYPE':{'No Apparent Injury':'O','Possible Injury':'C','Suspected Minor Injury':'B','Suspected Serious Injury':'A','Dead at Scene':'K','Dead on Arrival':'K','Died in Hospital':'K','Unknown':'U'},
 'WEATHER':{'Clear':'CLEAR','Partly Cloudy':'CLOUDY','Overcast':'CLOUDY','Clear or Partly Cloudy':'OTHER','Raining':'RAIN','Snowing':'SNOW','Fog or Smog or Smoke':'FOG_SMOKE','Severe Crosswind':'SEVERE_CROSSWIND','Sleet or Hail or Freezing Rain':'SLEET_HAIL','Blowing Sand or Dirt or Snow':'OTHER','Blowing Snow':'BLOWING_SNOW','Other':'OTHER','Unknown':'UNKNOWN'},
 'LIGHTING CONDITIONS':{'Daylight':'DAYLIGHT','Dawn':'DAWN','Dusk':'DUSK','Dark-Street Lights On':'DARK_LIGHTED','Dark-No Street Lights':'DARK_UNLIGHTED','Dark-Street Lights Off':'DARK_UNLIGHTED','Dark - Unknown Lightin':'DARK_UNKNOWN','Other':'OTHER','Unknown':'UNKNOWN'},
 'ROAD SURFACE CONDITIONS':{'Dry':'DRY','Wet':'WET','Ice':'ICE_FROST','Snow/Slush':'OTHER','Standing Water':'STANDING_WATER','Sand/Mud/Dirt':'SAND_MUD_DIRT_GRAVEL','Oil':'OIL','Other':'OTHER','Unknown':'UNKNOWN'}}
for field,mapping in maps.items():
    assert set(profile[field]) - {''} <= set(mapping), (field,set(profile[field])-set(mapping))
    for label,value in mapping.items():add(field,label,value,note='Combined source category retained in raw label; mapped to OTHER rather than split' if label in ['Clear or Partly Cloudy','Blowing Sand or Dirt or Snow','Snow/Slush'] else 'Explicit dictionary label crosswalk')
out=P/'config/enrichment/WA_SRFF_crosswalk.csv';out.parent.mkdir(exist_ok=True)
with out.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(out,len(rows),'unresolved',sum(r['status']=='UNRESOLVED' for r in rows))
