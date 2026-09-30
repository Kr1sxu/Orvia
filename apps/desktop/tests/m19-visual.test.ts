import {describe,it,expect,vi} from 'vitest';
import {readFileSync,mkdirSync,mkdtempSync,writeFileSync} from 'node:fs';
import path from 'node:path';
import {windowPresentation,attachWindowPresentation,taskbarAppId} from '../src/main/window-presentation';

describe('M19 presentation and native window boundaries',()=>{
  it('uses only fixed application metadata identities; unknown values cannot become arbitrary AppIds',()=>{
    expect(taskbarAppId(false,'never-read')).toBe('cn.orvia.desktop');
    const parent=path.resolve('artifacts/test-results/M19/appid-unit');mkdirSync(parent,{recursive:true});const root=mkdtempSync(path.join(parent,'app-'));
    for(const [value,expected]of [['cn.orvia.m19.visualtest','cn.orvia.m19.visualtest'],['arbitrary.untrusted','cn.orvia.desktop'],['cn.orvia.desktop','cn.orvia.desktop']]){
      writeFileSync(path.join(root,'package.json'),JSON.stringify({orviaAppId:value}));expect(taskbarAppId(true,root)).toBe(expected);
    }
  });
  it('resolves only trusted development/packaged icon roots and preserves native controls',()=>{
    const dev=windowPresentation('R',false,'P');const packaged=windowPresentation('R',true,'P');
    expect(dev.icon).toBe(path.join('R','apps/desktop/resources/icons/orvia.ico'));
    expect(packaged.icon).toBe(path.join('P','icons/orvia.ico'));
    expect(dev).toMatchObject({roundedCorners:true,thickFrame:true,titleBarStyle:'hidden',minWidth:760,minHeight:560,resizable:true,maximizable:true,minimizable:true,closable:true});
    expect(dev.transparent).toBeUndefined();expect(dev.webPreferences).toBeUndefined();
  });
  it('ignores modified/repeated keys; Escape affects only actual native fullscreen',()=>{
    let fullscreen=false;let callback:any;
    const show=vi.fn(),prevent=vi.fn();
    const window={once:vi.fn((_name,handler)=>handler()),show,webContents:{on:vi.fn((_name,handler)=>{callback=handler})},isFullScreen:()=>fullscreen,setFullScreen:vi.fn(value=>{fullscreen=value})};
    attachWindowPresentation(window as any);expect(show).toHaveBeenCalledOnce();
    const press=(key:string,rest={})=>callback({preventDefault:prevent},{type:'keyDown',key,isAutoRepeat:false,control:false,alt:false,meta:false,...rest});
    press('Escape');expect(prevent).not.toHaveBeenCalled();
    press('F11',{control:true});press('F11',{isAutoRepeat:true});expect(fullscreen).toBe(false);
    press('F11');expect(fullscreen).toBe(true);press('Escape');expect(fullscreen).toBe(false);
  });
  it('ships valid multi-size transparent PNG entries in the actual ICO',()=>{
    const ico=readFileSync('apps/desktop/resources/icons/orvia.ico');expect(ico.readUInt16LE(2)).toBe(1);expect(ico.readUInt16LE(4)).toBe(9);
    const sizes=[];
    for(let i=0;i<9;i++){const at=6+16*i,offset=ico.readUInt32LE(at+12),length=ico.readUInt32LE(at+8);expect(ico.subarray(offset,offset+8)).toEqual(Buffer.from([137,80,78,71,13,10,26,10]));expect(offset+length).toBeLessThanOrEqual(ico.length);sizes.push(ico[at]||256)}
    expect(sizes).toEqual([16,20,24,32,40,48,64,128,256]);
  });
  it('gives body/auxiliary/semantic colors readable contrast on their actual surfaces',()=>{
    function luminance(hex:string){const c=hex.match(/\w\w/g)!.map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722}
    const css=readFileSync('apps/desktop/src/renderer/style.css','utf8');
    const color=(name:string)=>css.match(new RegExp(`--${name}:#([0-9a-f]{6})`))![1];
    const disabled=css.match(/button:disabled\{color:#([0-9a-f]{6});background:#([0-9a-f]{6})/)!;
    const pairs=[[color('text'),color('bg')],[color('muted'),'ffffff'],['ffffff',color('accent')],[color('success'),color('success-soft')],[color('warning'),color('warning-soft')],[color('error'),color('error-soft')],[disabled[1],disabled[2]]];
    for(const [ink,paper]of pairs){const a=luminance(ink),b=luminance(paper);expect((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toBeGreaterThanOrEqual(4.5)}
  });
});
