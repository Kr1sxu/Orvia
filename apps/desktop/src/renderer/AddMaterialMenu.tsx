import React,{useEffect,useRef,useState} from 'react';
import {Icon} from './Visual';

/** 轻量菜单只选择原生入口，不接收路径；关闭菜单仅恢复用户主动进入的触发按钮焦点。 */
export function AddMaterialMenu({disabled,files,directory}:{disabled:boolean;files:()=>void;directory:()=>void}){
  const [open,setOpen]=useState(false),trigger=useRef<HTMLButtonElement>(null),menu=useRef<HTMLDivElement>(null);
  useEffect(()=>{if(open)menu.current?.querySelector<HTMLButtonElement>('button')?.focus();},[open]);
  useEffect(()=>{if(!open)return;const close=(event:PointerEvent)=>{if(!menu.current?.contains(event.target as Node)&&!trigger.current?.contains(event.target as Node))setOpen(false);};document.addEventListener('pointerdown',close);return()=>document.removeEventListener('pointerdown',close);},[open]);
  function close(){setOpen(false);trigger.current?.focus();}
  return <div className="material-menu"><button type="button" ref={trigger} aria-label="添加本地资料" aria-haspopup="menu" aria-expanded={open} disabled={disabled} onClick={()=>setOpen(!open)} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();setOpen(true);}}}><Icon name="plus"/></button>
    {open&&<div ref={menu} role="menu" aria-label="添加资料" onKeyDown={event=>{
      if(event.key==='Escape'){event.preventDefault();close();}
      if(event.key==='Tab')setOpen(false);
      if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const items=Array.from(menu.current!.querySelectorAll<HTMLButtonElement>('button'));const current=items.indexOf(document.activeElement as HTMLButtonElement);items[event.key==='Home'?0:event.key==='End'?items.length-1:(current+(event.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus();}
    }}><button type="button" role="menuitem" onClick={()=>{close();files();}}>添加文件（最多3个）</button><button type="button" role="menuitem" onClick={()=>{close();directory();}}>选择并授权文件夹</button></div>}
  </div>;
}
