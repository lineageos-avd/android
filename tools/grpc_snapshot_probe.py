#!/usr/bin/env python3
"""Validate an already-running, caller-owned private emulator; never discovers unrelated VMs."""
import argparse,base64,hashlib,json,subprocess,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--discovery',type=Path,required=True);p.add_argument('--proto',type=Path,required=True);p.add_argument('--adb',type=Path,required=True);p.add_argument('--adb-server-port',type=int,required=True);p.add_argument('--serial',required=True);p.add_argument('--avd-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--grpcurl',default='grpcurl');a=p.parse_args()
 state={}
 for line in a.discovery.read_text().splitlines():
  if '=' in line:
   key,value=line.split('=',1);state[key.strip()]=value.strip()
 token=state.get('grpc.token','');port=int(state.get('grpc.port','0'))
 if not token or not 0<port<65536:raise RuntimeError('Supplied discovery file lacks authenticated gRPC connection details')
 def rpc(method,data):
  command=[a.grpcurl,'-plaintext','-max-time','20','-max-msg-sz',str(64*1024*1024),'-import-path',str(a.proto.parent),'-proto',a.proto.name,'-H','authorization: Bearer '+token,'-d',json.dumps(data),'127.0.0.1:'+str(port),'android.emulation.control.EmulatorController/'+method]
  try: result=subprocess.run(command,text=True,capture_output=True,timeout=30)
  except subprocess.TimeoutExpired:raise RuntimeError('gRPC '+method+' timed out') from None
  if result.returncode:raise RuntimeError('gRPC '+method+' failed: '+result.stderr.replace(token,'<redacted>'))
  return json.loads(result.stdout or '{}')
 status=rpc('getStatus',{})
 if not status.get('booted'):raise RuntimeError('Guest is not booted yet')
 before=rpc('getClipboard',{}).get('text','')
 text='Emulator Hub source-engine verification 验证'
 rpc('setClipboard',{'text':text})
 if rpc('getClipboard',{}).get('text')!=text:raise RuntimeError('Unicode clipboard round trip failed')
 rpc('setClipboard',{'text':before})
 rgba=rpc('getScreenshot',{'format':'RGBA8888','width':320,'height':640})
 fmt=rgba.get('format',{});pixels=base64.b64decode(rgba.get('image',''),validate=True)
 if not pixels or len(pixels)!=fmt.get('width',0)*fmt.get('height',0)*4:raise RuntimeError('RGBA screenshot dimensions/data are invalid')
 png=base64.b64decode(rpc('getScreenshot',{'format':'PNG'}).get('image',''),validate=True)
 if not png.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('PNG screenshot is invalid')
 a.output.mkdir(parents=True,exist_ok=True);screenshot=a.output/'grpc-screenshot.png';screenshot.write_bytes(png)
 def adb(*command):
  result=subprocess.run([str(a.adb),'-P',str(a.adb_server_port),'-s',a.serial,*command],text=True,capture_output=True,timeout=120)
  if result.returncode or any(line.startswith('KO:') for line in result.stdout.splitlines()):raise RuntimeError('ADB operation failed: '+result.stdout+result.stderr)
  return result.stdout.strip()
 snapshot='hub_grpc_qa';adb('emu','avd','snapshot','save',snapshot)
 descriptor=a.avd_dir/'snapshots'/snapshot/'snapshot.pb'
 if not descriptor.is_file():raise RuntimeError('Emulator did not persist the requested snapshot descriptor')
 adb('emu','avd','snapshot','load',snapshot)
 # Snapshot restore reconnects the guest ADB transport asynchronously.
 adb('wait-for-device')
 restored_kernel=adb('shell','uname','-r')
 deadline=time.monotonic()+30
 while not rpc('getStatus',{}).get('booted'):
  if time.monotonic()>deadline:raise RuntimeError('Guest did not recover after snapshot restore')
  time.sleep(0.5)
 result={'status':'passed','engine_status':{key:status[key] for key in ('version','booted','vmConfig') if key in status},'grpc_authenticated':True,'clipboard_unicode':True,'rgba_width':fmt['width'],'rgba_height':fmt['height'],'rgba_bytes':len(pixels),'png_sha256':hashlib.sha256(png).hexdigest(),'snapshot':snapshot,'snapshot_descriptor':str(descriptor),'kernel':restored_kernel}
 (a.output/'grpc-snapshot-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
