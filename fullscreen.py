from terminal_ui import run
import tarrivox,subprocess

def operation(ui,fn):
 try:ui.external(fn)
 except (ValueError,OSError,subprocess.SubprocessError) as exc:ui.message("Stopped: "+str(exc))


def session(ui):
 while True:
  choice=ui.menu('Encrypted backup - original confirmations apply',['Local system backup','Chosen directory backup','Upload existing encrypted backup','Quit'])
  if choice is None or choice==3:return
  if choice==0:
   operation(ui,lambda:tarrivox.backup('/','~/tarrivox-backups'))
  elif choice==1:
   source=ui.prompt('Source directory (Esc cancels)')
   if not source:continue
   output=ui.prompt('Output directory (Esc cancels)')
   if not output:continue
   operation(ui,lambda:tarrivox.backup(source,output))
  elif choice==2:
   archive=ui.prompt('Existing encrypted archive path (Esc cancels)')
   if not archive:continue
   repo=ui.prompt('New owner/repository (Esc cancels)')
   if not repo:continue
   operation(ui,lambda:tarrivox.upload(archive,repo))
if __name__=='__main__':
 import sys
 if len(sys.argv)>1:raise SystemExit(tarrivox.main())
 raise SystemExit(run('Tarrivox',session))
