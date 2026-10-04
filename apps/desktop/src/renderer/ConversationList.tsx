import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import type {ConversationSummary} from '../main/chat-contracts';
import {taskLabels} from './chat-state';
import {Icon} from './Visual';

type Props={items:ConversationSummary[];current?:string;loading:boolean;disabled:boolean;open:(id:string)=>void;pin:(item:ConversationSummary)=>Promise<void>;rename:(id:string,title:string)=>Promise<boolean>;remove:(id:string)=>Promise<void>};

/** 菜单用固定定位portal避开历史列表裁剪；只发固定会话接口，不携带授权字段。 */
export function ConversationList({items,current,loading,disabled,open,pin,rename,remove}:Props){
  const [menu,setMenu]=useState<{item:ConversationSummary;button:HTMLButtonElement}>();
  const [edit,setEdit]=useState<ConversationSummary>();
  const [title,setTitle]=useState('');
  const [position,setPosition]=useState({left:0,top:0});
  const panel=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null),input=useRef<HTMLInputElement>(null);
  const close=(focus=false)=>{if(focus&&menu?.button.isConnected)menu.button.focus();setMenu(undefined);};
  useEffect(()=>{setMenu(undefined);setEdit(undefined);},[current]);
  useEffect(()=>{if(disabled)setMenu(undefined);},[disabled]);
  useLayoutEffect(()=>{
    if(!menu)return;
    const bounds=menu.button.getBoundingClientRect(),height=panel.current?.offsetHeight??150;
    setPosition({left:Math.max(8,Math.min(bounds.right-180,innerWidth-188)),top:Math.max(8,Math.min(bounds.bottom+4,innerHeight-height-8))});
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const outside=(event:PointerEvent)=>{if(!panel.current?.contains(event.target as Node)&&!menu.button.contains(event.target as Node))close();};
    const hide=()=>close();
    document.addEventListener('pointerdown',outside);window.addEventListener('resize',hide);document.querySelector('.sidebar nav')?.addEventListener('scroll',hide);
    return()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',hide);document.querySelector('.sidebar nav')?.removeEventListener('scroll',hide);};
  },[menu]);
  useEffect(()=>{if(edit){dialog.current?.showModal();input.current?.select();}else dialog.current?.close();},[edit]);
  return <>
    <nav aria-label="历史会话" aria-busy={loading}>
      {items.map(item=><div className="conversation-row" key={item.id}>
        <button className={`conversation-open ${current===item.id?'selected':''}`} title={item.title} aria-label={item.title} aria-current={current===item.id?'page':undefined} onClick={()=>{close();open(item.id);}}><span className="history-title">{item.pinned&&<Icon name="pin"/>}{item.title}</span><small>{item.pinned?'已置顶 · ':''}{taskLabels[item.status??'draft']??item.status}</small></button>
        <button className="conversation-more" aria-label={`更多操作：${item.title}`} aria-haspopup="menu" aria-expanded={menu?.item.id===item.id} disabled={disabled} onClick={event=>menu?.item.id===item.id?close(true):setMenu({item,button:event.currentTarget})}><Icon name="more"/></button>
      </div>)}
      {loading?<p role="status" className="muted">正在读取会话…</p>:!items.length&&<p className="muted">从第一个问题开始。</p>}
    </nav>
    {menu&&createPortal(<div ref={panel} role="menu" aria-label="会话操作" className="conversation-menu" style={position} onKeyDown={event=>{
      const nodes=Array.from(panel.current?.querySelectorAll<HTMLButtonElement>('button')??[]),index=nodes.indexOf(document.activeElement as HTMLButtonElement);
      if(event.key==='Escape'){event.preventDefault();close(true);}
      else if(event.key==='Tab')close();
      else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();nodes[event.key==='Home'?0:event.key==='End'?nodes.length-1:(index+(event.key==='ArrowDown'?1:-1)+nodes.length)%nodes.length]?.focus();}
    }}>
      <button role="menuitem" onClick={()=>{const item=menu.item;close(true);void pin(item);}}><Icon name="pin"/>{menu.item.pinned?'取消置顶':'置顶'}</button>
      <button role="menuitem" onClick={()=>{setTitle(menu.item.title);setEdit(menu.item);close(true);}}><Icon name="edit"/>重命名</button>
      <button role="menuitem" className="danger" onClick={()=>{const id=menu.item.id;close(true);void remove(id);}}><Icon name="trash"/>删除</button>
    </div>,document.body)}
    <dialog ref={dialog} className="conversation-rename" aria-label="重命名对话" onCancel={()=>setEdit(undefined)} onClose={()=>setEdit(undefined)}>
      <form onSubmit={event=>{event.preventDefault();if(edit&&title.trim())void rename(edit.id,title.trim()).then(ok=>{if(ok)setEdit(undefined);});}}>
        <h2>重命名对话</h2><label>对话名称<input ref={input} autoFocus maxLength={100} value={title} onChange={event=>setTitle(event.target.value)} disabled={disabled}/></label>
        {!title.trim()&&<p role="status">名称不能为空。</p>}
        <div className="row"><button type="button" onClick={()=>setEdit(undefined)} disabled={disabled}>取消</button><button type="submit" className="primary" disabled={disabled||!title.trim()}>保存名称</button></div>
      </form>
    </dialog>
  </>;
}
