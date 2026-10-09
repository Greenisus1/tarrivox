#!/usr/bin/env python3
"""Tarrivox: encrypted local backups, optional private GitHub release upload."""
import argparse,datetime,json,os,pathlib,re,shutil,subprocess,sys,tempfile
MAX_UPLOAD=90*1024*1024

def require(*programs):
    missing=[p for p in programs if not shutil.which(p)]
    if missing: raise ValueError('Missing programs: '+', '.join(missing))

def confirm(text):
    return input(text+' [y/N] ').strip().lower()=='y'

def archive_command(source,output):
    cmd=['tar','--one-file-system','--numeric-owner','-czpf','-']
    # Exclude pseudo-filesystems and other mounts. A single filesystem isn't a full disk image.
    if source==pathlib.Path('/'):
        cmd+=['--exclude=./'+n for n in ['proc','sys','dev','run','tmp','media','mnt','lost+found']]
        cmd+=['--exclude=.'+str(output)]
    elif output.is_relative_to(source):
        cmd+=['--exclude=./'+str(output.relative_to(source))]
    return cmd+['-C',str(source),'.']

def backup(source,output,ask=confirm):
    require('tar','gpg')
    source=pathlib.Path(source).resolve(strict=True)
    output=pathlib.Path(output).expanduser().resolve()
    if not source.is_dir(): raise ValueError('Source must be a directory.')
    if output==source: raise ValueError('Output directory must differ from source directory.')
    if not sys.stdin.isatty(): raise ValueError('Use an interactive terminal for encryption passphrase entry.')
    if not ask('Back up '+str(source)+' to encrypted local directory '+str(output)+'? This can take a long time.'):
        return None
    output.mkdir(parents=True,exist_ok=True);output.chmod(0o700)
    destination=output/('tarrivox-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.tar.gz.gpg')
    if destination.exists(): raise ValueError('Destination already exists; wait and try again.')
    # Reserve unique mode0600 temporary file. Plain archive only traverses a pipe, never disk.
    fd,tmp=tempfile.mkstemp(prefix='.tarrivox-',dir=output);os.close(fd)
    producer=None
    try:
        cmd=archive_command(source,output)
        if source==pathlib.Path('/') and os.geteuid()!=0:
            require('sudo');subprocess.run(['sudo','-v'],check=True);cmd=['sudo']+cmd
        env=dict(os.environ)
        try:env['GPG_TTY']=os.ttyname(sys.stdin.fileno())
        except OSError:pass
        producer=subprocess.Popen(cmd,stdout=subprocess.PIPE)
        try:
            encryption=subprocess.run(['gpg','--yes','--symmetric','--cipher-algo','AES256','--output',tmp],stdin=producer.stdout,env=env)
        finally:
            producer.stdout.close()
        if encryption.returncode:
            if producer.poll() is None:producer.terminate()
            producer.wait();raise ValueError('Encryption stopped or failed; partial output removed.')
        if producer.wait()!=0:raise ValueError('tar failed or files changed during backup; partial output removed. Stop changing files and retry.')
        if pathlib.Path(tmp).stat().st_size==0:raise ValueError('Empty encrypted archive.')
        os.chmod(tmp,0o600)
        # Never overwrite an earlier backup.
        os.link(tmp,destination);os.unlink(tmp)
        note=destination.with_suffix(destination.suffix+'.txt')
        note.write_text('Tarrivox encrypted tar snapshot of '+str(source)+'\nUTC time: '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'\nNot a disk image. Only one filesystem included. Root backup excludes proc/sys/dev/run/tmp/media/mnt and output directory. External mounts/boot partitions are not included.\nRestore manually to a separate directory using GPG then tar; inspect contents first. No automatic overwrite/restore is provided.\n')
        note.chmod(0o600)
        print('Encrypted backup saved:',destination)
        return destination
    finally:
        if producer and producer.poll() is None:producer.terminate();producer.wait()
        try:os.unlink(tmp)
        except FileNotFoundError:pass

def upload(archive,repo,ask=confirm,run=subprocess.run):
    require('gh')
    archive=pathlib.Path(archive).resolve(strict=True)
    if not archive.is_file() or not archive.name.endswith('.tar.gz.gpg'):raise ValueError('Choose a Tarrivox .tar.gz.gpg file.')
    if archive.stat().st_size==0 or archive.stat().st_size>MAX_UPLOAD:raise ValueError('Upload accepts encrypted archives up to 90 MiB. Keep larger backups local.')
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Repository must be owner/name.')
    run(['gh','auth','status'],check=True)
    result=run(['gh','api','user'],check=True,capture_output=True,text=True)
    account=json.loads(result.stdout)['login']
    owner,name=repo.split('/')
    if owner.lower()!=account.lower():raise ValueError('Destination owner must be the authenticated gh user: '+account)
    check=run(['gh','api','repos/'+repo],capture_output=True,text=True)
    if check.returncode==0:raise ValueError('Destination already exists. Choose a new private backup repository.')
    if '404' not in check.stderr:raise ValueError('Could not verify destination is absent. No upload attempted.')
    if not ask('Upload encrypted archive '+archive.name+' ('+str(archive.stat().st_size)+' bytes) to NEW PRIVATE '+repo+'? GitHub will receive ciphertext and filename.'):
        return None
    run(['gh','repo','create',repo,'--private'],check=True)
    result=run(['gh','api','repos/'+repo],check=True,capture_output=True,text=True)
    state=json.loads(result.stdout)
    if state.get('private') is not True or state.get('full_name','').lower()!=repo.lower():raise ValueError('Private destination verification failed. No archive uploaded.')
    try:
        run(['gh','release','create','backup-1',str(archive),'--repo',repo,'--title','Tarrivox encrypted backup','--notes','Encrypted local snapshot. Keep its passphrase separately.'],check=True)
        result=run(['gh','api','repos/'+repo+'/releases/tags/backup-1'],check=True,capture_output=True,text=True)
        release=json.loads(result.stdout)
        if not any(a.get('name')==archive.name and a.get('size')==archive.stat().st_size for a in release.get('assets',[])):
            raise ValueError('Upload size/name verification failed. Local backup retained; inspect repository before retrying.')
        print('Verified private encrypted backup:',release['html_url'])
        return release['html_url']
    except Exception:
        print('Upload incomplete/unverified. Local archive retained. Repository may exist; inspect it before retrying.',file=sys.stderr)
        raise

def main():
    parser=argparse.ArgumentParser(description='Tarrivox encrypted local backup. Optional private GitHub release upload.')
    sub=parser.add_subparsers(dest='command')
    b=sub.add_parser('backup');b.add_argument('--source',default='/');b.add_argument('--output',default='~/tarrivox-backups')
    u=sub.add_parser('upload');u.add_argument('archive');u.add_argument('repo')
    args=parser.parse_args()
    try:
        if args.command=='backup':backup(args.source,args.output)
        elif args.command=='upload':upload(args.archive,args.repo)
        else:
            while True:
                print('\nTarrivox\n1 Encrypted local system backup\n2 Back up a chosen directory\n3 Upload an existing encrypted backup (new private GitHub repo)\n4 Quit')
                choice=input('Choice: ').strip()
                if choice in ('4','q','Q'):break
                if choice=='1':backup('/', '~/tarrivox-backups')
                elif choice=='2':backup(input('Source directory: '),input('Output directory: '))
                elif choice=='3':upload(input('Encrypted archive path: '),input('New owner/repository: '))
    except (ValueError,OSError,subprocess.SubprocessError,KeyError,json.JSONDecodeError) as exc:
        print('Stopped:',exc,file=sys.stderr);return 1
    except (KeyboardInterrupt,EOFError):print('\nStopped.');return 1
    return 0
if __name__=='__main__':sys.exit(main())
