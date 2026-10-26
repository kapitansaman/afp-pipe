"""Bind capability evidence to this repository's explicitly rotated credential set.
No credential values or credential fingerprints are persisted.
"""
from .queue import DATA,load_json

def binding(data=DATA):
 config=load_json(data/'config.json')
 return {k:config[k] for k in ('repository','credential_set_id') if config.get(k)}

def trusted(row,data=DATA):
 expected=binding(data)
 return all(row.get(k)==v for k,v in expected.items())
