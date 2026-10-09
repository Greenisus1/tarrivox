import hashlib,json,os,pathlib,subprocess,tempfile,unittest
from unittest import mock
import tarrivox
ROOT=pathlib.Path(__file__).resolve().parent
class Tests(unittest.TestCase):
 def test_install(self):self.assertEqual(subprocess.run(['bash','app-store.sh','install'],cwd=ROOT).returncode,0)
 def test_marker(self):self.assertIn('# pi-app-store: 1',(ROOT/'app-store.sh').read_text().splitlines()[:5])
 def test_version(self):self.assertEqual(json.loads((ROOT/'app-version.json').read_text())['version'],'1.0.0')
 def test_menu_exit(self):
  r=subprocess.run(['python3','tarrivox.py'],cwd=ROOT,input='4\n',text=True,capture_output=True);self.assertEqual(r.returncode,0);self.assertIn('Choice:',r.stdout)
 def test_no_noninteractive_backup(self):
  with tempfile.TemporaryDirectory() as home:
   r=subprocess.run(['python3','tarrivox.py','backup','--source',home,'--output',home+'/out'],cwd=ROOT,capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('interactive',r.stderr);self.assertFalse((pathlib.Path(home)/'out').exists())
 def test_archive_exclusions(self):
  cmd=tarrivox.archive_command(pathlib.Path('/'),pathlib.Path('/home/a/backups'))
  self.assertIn('--one-file-system',cmd);self.assertIn('--exclude=./home/a/backups',cmd);self.assertIn('--exclude=./proc',cmd)
 def test_backup_cancel(self):
  with tempfile.TemporaryDirectory() as home,mock.patch('sys.stdin.isatty',return_value=True):
   self.assertIsNone(tarrivox.backup(home,home+'/out',ask=lambda _:False));self.assertFalse((pathlib.Path(home)/'out').exists())
 def test_real_tar_and_encryption_roundtrip(self):
  # Test-only known disposable passphrase. Production never accepts a passphrase flag.
  with tempfile.TemporaryDirectory() as home,mock.patch('sys.stdin.isatty',return_value=True):
   h=pathlib.Path(home);source=h/'source';source.mkdir();(source/'data.txt').write_text('roundtrip test data\n');output=source/'backups'
   realrun=subprocess.run
   def test_run(cmd,**kwargs):
    if cmd[0]=='gpg':cmd=cmd[:1]+['--batch','--pinentry-mode','loopback','--passphrase','disposable-test-only']+cmd[1:]
    return realrun(cmd,**kwargs)
   with mock.patch('tarrivox.subprocess.run',side_effect=test_run):archive=tarrivox.backup(source,output,ask=lambda _:True)
   self.assertTrue(archive.is_file());self.assertEqual(archive.stat().st_mode&0o777,0o600)
   plain=realrun(['gpg','--batch','--pinentry-mode','loopback','--passphrase','disposable-test-only','--decrypt',str(archive)],capture_output=True,check=True).stdout
   result=realrun(['tar','-tzf','-'],input=plain,capture_output=True,check=True).stdout.decode()
   self.assertIn('./data.txt',result);self.assertNotIn('backups',result)
   bad=realrun(['gpg','--batch','--pinentry-mode','loopback','--passphrase','wrong-test-only','--decrypt',str(archive)],capture_output=True)
   self.assertNotEqual(bad.returncode,0)
 def test_encryption_failure_cleanup(self):
  with tempfile.TemporaryDirectory() as home,mock.patch('sys.stdin.isatty',return_value=True):
   h=pathlib.Path(home);source=h/'source';source.mkdir();(source/'x').write_text('x')
   with mock.patch('tarrivox.subprocess.run',return_value=subprocess.CompletedProcess([],1)):
    with self.assertRaises(ValueError):tarrivox.backup(source,h/'out',ask=lambda _:True)
   self.assertEqual(list((h/'out').iterdir()),[])
 def run_upload(self,private=True,owner='tester',cancel=False,size=100,fail=False):
  with tempfile.TemporaryDirectory() as home,mock.patch('tarrivox.require'):
   f=pathlib.Path(home)/'tarrivox-test.tar.gz.gpg';f.write_bytes(b'x'*size);calls=[]
   def run(cmd,**kwargs):
    calls.append(cmd)
    if cmd==['gh','api','user']:return subprocess.CompletedProcess(cmd,0,json.dumps({'login':owner}),'')
    if cmd==['gh','api','repos/tester/backup']:
     count=sum(c==cmd for c in calls)
     if count==1:return subprocess.CompletedProcess(cmd,1,'','HTTP 404')
     return subprocess.CompletedProcess(cmd,0,json.dumps({'private':private,'full_name':'tester/backup'}),'')
    if cmd[:3]==['gh','release','create'] and fail:raise subprocess.CalledProcessError(1,cmd)
    if cmd==['gh','api','repos/tester/backup/releases/tags/backup-1']:
     return subprocess.CompletedProcess(cmd,0,json.dumps({'assets':[{'name':f.name,'size':size}],'html_url':'https://example.invalid/test-only'}),'')
    return subprocess.CompletedProcess(cmd,0,'','')
   return f,calls,tarrivox.upload(f,'tester/backup',ask=lambda _:not cancel,run=run)
 def test_mock_upload_private_and_no_git(self):
  _,calls,url=self.run_upload();self.assertEqual(url,'https://example.invalid/test-only');self.assertTrue(all(c[0]=='gh' for c in calls));self.assertIn(['gh','repo','create','tester/backup','--private'],calls)
 def test_upload_cancel(self):
  _,calls,url=self.run_upload(cancel=True);self.assertIsNone(url);self.assertFalse(any(c[:3]==['gh','repo','create'] for c in calls))
 def test_public_destination_blocks_upload(self):
  with self.assertRaises(ValueError):self.run_upload(private=False)
 def test_wrong_owner_blocks_upload(self):
  with self.assertRaises(ValueError):self.run_upload(owner='wrong')
 def test_bad_suffix(self):
  with tempfile.NamedTemporaryFile(suffix='.txt') as f,mock.patch('tarrivox.require'):
   with self.assertRaises(ValueError):tarrivox.upload(f.name,'tester/repo')
 def test_upload_size_limit(self):
  with tempfile.NamedTemporaryFile(suffix='.tar.gz.gpg') as f,mock.patch('tarrivox.require'):
   f.truncate(tarrivox.MAX_UPLOAD+1)
   with self.assertRaises(ValueError):tarrivox.upload(f.name,'tester/repo')
if __name__=='__main__':unittest.main()
