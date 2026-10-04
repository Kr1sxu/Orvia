import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import {DocumentCard,documentStatus,documentFailure} from '../src/renderer/DocumentCards';
import {SynthesisResult,SynthesisPreviewCard} from '../src/renderer/SynthesisCards';
import type {ChatMessage,DocumentEvidence,SynthesisPreview} from '../src/main/chat-contracts';

const id='a'.repeat(64);
const source:DocumentEvidence={evidence_id:id,content_hash:id,file_hash:'b'.repeat(64),title:'论文.pdf',format:'pdf',accessed_at:'2026-10-04',total_units:2,truncated:false,missing_units:[],error:null,preview_truncated:true,units:[{number:1,locator:'第 1 页',text:'资料正文',method:'text',confidence:null,error:null}]};
it.each(['pdf','docx','pptx','png'])('%s 的短摘录不误报全文缺失，技术字段折叠保留',format=>{
 const item={...source,format} as DocumentEvidence;
 expect(documentStatus(item)).toBe('已准备回答');
 const html=renderToStaticMarkup(<DocumentCard message={{data:{items:[item],operation:'attach',error:null}} as ChatMessage} disabled={false} show={()=>{}}/>);
 expect(html).toContain('<summary>查看来源详情</summary>');
 expect(html.indexOf(id)).toBeGreaterThan(html.indexOf('<details>'));
 expect(html.slice(0,html.indexOf('<details>'))).not.toContain('OCR');
});
it('部分可用、全空、错误和 OCR 不可用各有正确状态和下一步',()=>{
 expect(documentStatus({...source,missing_units:[1]})).toBe('部分内容无法读取');
 expect(documentStatus({...source,missing_units:[1,2]})).toBe('无法回答');
 expect(documentStatus({...source,error:{code:'ocr_unavailable',message:'内部'}})).toBe('无法回答');
 expect(documentFailure('ocr_unavailable')).toContain('含可选中文字');
 expect(documentFailure('worker_failed')).toContain('重启');
});
const fragment={citation:`document:${id}:1:0`,kind:'document' as const,evidence_id:id,locator:'第 1 页',unit:1,chunk:0,text:'资料正文'};
const coverage={kind:'document' as const,evidence_id:id,title:'论文.pdf',accessed_at:'2026-10-04',selected_chunks:1,available_chunks:3,source_truncated:false,missing_units:[2],ocr_available:false,ocr_selected:false};
it('引用使用文件名页码，发送预览不暴露身份但保留准确正文和范围',()=>{
 const preview:SynthesisPreview={mode:'summary',question:'总结',supplier:'Main · deepseek-flash',fragments:[fragment],coverage:[coverage],revision:id};
 const html=renderToStaticMarkup(<SynthesisPreviewCard preview={preview} disabled={false} confirm={()=>{}} close={()=>{}}/>);
 expect(html).not.toContain(id);expect(html).toContain('资料正文');expect(html).toContain('部分内容未能读取');expect(html).toContain('原生确认框');
 const result=renderToStaticMarkup(<SynthesisResult message={{data:{answer:'总结',claims:[{text:'要点',kind:'fact',citations:[fragment.citation]}],citations:[fragment],coverage:[coverage],revision:id,model:'deepseek-flash',usage:{}}} as ChatMessage} show={()=>{}} compose={()=>{}}/>);
 expect(result).not.toContain(fragment.citation);expect(result).toContain('论文.pdf');expect(result).toContain('第 1 页');expect(result).toContain('未覆盖文件全文');
});
