import json
import subprocess
import sys
import unittest
from pathlib import Path


class RegressionBudgetTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'),'Linux deployment memory limit')
    def test_large_allocation_is_rejected_only_inside_test_process(self):
        import resource
        before=resource.getrlimit(resource.RLIMIT_DATA)
        code='''from scripts.healthcheck_suite import limit_python_memory
limit_python_memory()
try:
    value=bytearray(512*1024*1024)
except MemoryError:
    print('bounded')
else:
    raise RuntimeError('allocation was not bounded')
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'bounded')
        self.assertEqual(resource.getrlimit(resource.RLIMIT_DATA),before)


if __name__=='__main__':unittest.main()
