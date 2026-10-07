"""V4-009合成进程：只写明确合成marker，不读取个人正文/环境快照。"""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys
import time

mode=sys.argv[1];marker=Path(sys.argv[2])
def write(**values):marker.write_text(json.dumps({'pid':os.getpid(),**values}),encoding='utf-8')
if mode=='exit':
    write(ready=True);time.sleep(.15);sys.exit(int(sys.argv[3]))
if mode=='sleep':
    write(ready=True);time.sleep(30);sys.exit(0)
if mode=='env':
    ok=not any(os.environ.get(name) for name in ('ORVIA_SYNTHETIC_API_KEY','ORVIA_SYNTHETIC_TOKEN','HTTPS_PROXY'))
    write(ready=True,clean=ok,cwd_matches=str(Path.cwd())==sys.argv[3]);sys.exit(0 if ok else 91)
if mode not in ('window-close','window-ignore'):raise SystemExit(92)
u=ctypes.WinDLL('user32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
k.GetModuleHandleW.argtypes=[w.LPCWSTR];k.GetModuleHandleW.restype=w.HMODULE
callback_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
class WNDCLASS(ctypes.Structure):
    _fields_=[('style',w.UINT),('lpfnWndProc',callback_type),('cbClsExtra',ctypes.c_int),('cbWndExtra',ctypes.c_int),('hInstance',w.HINSTANCE),('hIcon',w.HICON),('hCursor',w.HANDLE),('hbrBackground',w.HANDLE),('lpszMenuName',w.LPCWSTR),('lpszClassName',w.LPCWSTR)]
u.DefWindowProcW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.DefWindowProcW.restype=ctypes.c_ssize_t
u.DestroyWindow.argtypes=[w.HWND];u.DestroyWindow.restype=w.BOOL
u.PostQuitMessage.argtypes=[ctypes.c_int]
messages=0
def callback(hwnd,message,wp,lp):
    global messages
    if message==0x10:
        messages+=1;write(ready=True,messages=messages)
        if mode=='window-close':u.DestroyWindow(hwnd)
        return 0
    if message==2:u.PostQuitMessage(0);return 0
    return u.DefWindowProcW(hwnd,message,wp,lp)
fn=callback_type(callback);instance=k.GetModuleHandleW(None)
cls=WNDCLASS(0,fn,0,0,instance,None,None,None,None,'OrviaSyntheticV4009')
u.RegisterClassW.argtypes=[ctypes.POINTER(WNDCLASS)];u.RegisterClassW.restype=w.WORD
u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,w.LPVOID];u.CreateWindowExW.restype=w.HWND
if not u.RegisterClassW(ctypes.byref(cls)):raise SystemExit(93)
window=u.CreateWindowExW(0,cls.lpszClassName,'Orvia synthetic process',0,0,0,80,80,None,None,instance,None)
if not window:raise SystemExit(94)
write(ready=True,messages=0)
u.GetMessageW.argtypes=[ctypes.POINTER(w.MSG),w.HWND,w.UINT,w.UINT];u.GetMessageW.restype=ctypes.c_int
u.TranslateMessage.argtypes=[ctypes.POINTER(w.MSG)];u.DispatchMessageW.argtypes=[ctypes.POINTER(w.MSG)]
msg=w.MSG()
while u.GetMessageW(ctypes.byref(msg),None,0,0)>0:
    u.TranslateMessage(ctypes.byref(msg));u.DispatchMessageW(ctypes.byref(msg))
