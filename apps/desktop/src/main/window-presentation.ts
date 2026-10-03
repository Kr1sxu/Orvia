import type { BrowserWindowConstructorOptions, BrowserWindow } from 'electron';
import path from 'node:path';
import {readFileSync} from 'node:fs';

/** AppId只改变Windows分组/图标；只读可信安装元数据中的固定值，不参与业务授权。 */
export function taskbarAppId(packaged:boolean,applicationPath:string):string {
  if(!packaged)return 'cn.orvia.desktop';
  const metadata=JSON.parse(readFileSync(path.join(applicationPath,'package.json'),'utf8')) as {orviaAppId?:unknown};
  if(metadata.orviaAppId==='cn.orvia.m19.visualtest')return 'cn.orvia.m19.visualtest';
  if(metadata.orviaAppId==='cn.orvia.m20.fulltest')return 'cn.orvia.m20.fulltest';
  return 'cn.orvia.desktop';
}

/** 只从可信应用目录定位品牌资源；renderer不能传路径或改变窗口构造参数。 */
export function windowPresentation(root:string,packaged:boolean,resourcesPath:string):BrowserWindowConstructorOptions {
  return {width:1120,height:880,minWidth:760,minHeight:560,title:'序航 Orvia',backgroundColor:'#f6f7f8',show:false,
    icon:path.join(packaged?resourcesPath:path.join(root,'apps/desktop/resources'),'icons/orvia.ico'),
    autoHideMenuBar:true,titleBarStyle:'hidden',titleBarOverlay:{color:'#f6f7f8',symbolColor:'#22272e',height:42},
    // 不透明原生窗口保留系统阴影/边缘缩放。Win11普通窗圆角，最大化/贴靠/全屏由DWM取消圆角。
    roundedCorners:true,thickFrame:true,resizable:true,minimizable:true,maximizable:true,closable:true,
  };
}

/** 原生控制覆盖层承担拖动/双击/最小化/最大化/关闭，不新增renderer控制IPC。 */
export function attachWindowPresentation(window:BrowserWindow) {
  window.once('ready-to-show',()=>window.show());
  window.webContents.on('before-input-event',(event,input)=>{
    if(input.type!=='keyDown'||input.isAutoRepeat||input.control||input.alt||input.meta)return;
    if(input.key==='F11'){event.preventDefault();window.setFullScreen(!window.isFullScreen());}
    else if(input.key==='Escape'&&window.isFullScreen()){event.preventDefault();window.setFullScreen(false);}
  });
}
