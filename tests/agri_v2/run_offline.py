"""Run mocked unit tests without inheriting the live provider circuit file.
The real circuit is never changed; individual circuit tests retain their fixtures.
"""
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from automation.agri_v2 import recovery

def main():
 with tempfile.TemporaryDirectory(prefix='afp-offline-circuit-') as d:
  with patch.object(recovery,'OUT',Path(d)):
   suite=unittest.defaultTestLoader.discover(str(ROOT/'tests/agri_v2'))
   result=unittest.TextTestRunner(verbosity=1).run(suite)
 return 0 if result.wasSuccessful() else 1

if __name__=='__main__':sys.exit(main())
