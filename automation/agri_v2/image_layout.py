"""Owner-selected production layout: one featured image and one inline image.
Legacy scene recipes remain available for explicit diagnostics, not production.
"""
PRODUCTION_IMAGE_ROLES=(1,2)
IMAGE_LAYOUT='featured-plus-one-inline-v1'

SINGLE_IMAGE_LAYOUT='single-approved-featured-v2'
def roles_for(folder):
 from pathlib import Path
 from .queue import load_json
 p=Path(folder)/'image-selection.json'
 if not p.exists():return PRODUCTION_IMAGE_ROLES
 r=load_json(p);roles=r.get('selected_roles')
 if roles not in ([1],[2],[1,2]) or any(type(k)is not int for k in roles):raise ValueError('Invalid publication image roles')
 return tuple(roles)
def layout_for(roles):return SINGLE_IMAGE_LAYOUT if len(roles)==1 else IMAGE_LAYOUT
