"""Explicit, version-specific XY conversion; no inferred CRS or geocoding.

Projected units, datum and axis order come from reviewed configuration. Original
XY remain untouched in the source row. Zero sentinels become missing; malformed
nonblank values remain invalid. Broad bounds are checked by the calling engine.
"""
from functools import lru_cache
from math import isfinite

@lru_cache(maxsize=8)
def _transformer(source_crs):
    from pyproj import Transformer
    return Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)

def coordinate_values(row, fields, version):
    definition=version.get('coordinate_transform')
    if not definition:
        return (row[fields['latitude']].strip() if 'latitude' in fields else '',
                row[fields['longitude']].strip() if 'longitude' in fields else '')
    if definition.get('target_crs')!='EPSG:4326' or definition.get('always_xy') is not True:
        raise ValueError('Only explicitly configured XY to EPSG:4326 is supported')
    xraw=row[fields['x_coordinate']].strip();yraw=row[fields['y_coordinate']].strip()
    if not xraw or not yraw:return ('','') if not xraw and not yraw else ('INVALID','INVALID')
    try:x=float(xraw);y=float(yraw)
    except ValueError:return 'INVALID','INVALID'
    if not isfinite(x) or not isfinite(y):return 'INVALID','INVALID'
    if definition.get('zero_is_missing') and (x==0 or y==0):return '',''
    lon,lat=_transformer(definition['source_crs']).transform(x,y,errcheck=True)
    if not isfinite(lon) or not isfinite(lat):return 'INVALID','INVALID'
    digits=definition.get('decimal_places',8)
    return f'{lat:.{digits}f}',f'{lon:.{digits}f}'
