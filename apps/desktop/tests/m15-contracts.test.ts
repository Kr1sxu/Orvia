import {describe,it,expect} from 'vitest';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {chatSynthesisPreviewSchema,chatSynthesisGenerateSchema,synthesisPreviewSchema,chatMessageSchema} from '../src/main/chat-contracts';
import {SynthesisPreviewCard,SynthesisResult} from '../src/renderer/SynthesisCards';

const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c',hash='a'.repeat(64);
const source={kind:'document' as const,evidence_id:hash};
const coverage={...source,title:'合成资料',accessed_at:'2026-09-29',selected_chunks:1,available_chunks:3,source_truncated:true,missing_units:[2],ocr_available:true,ocr_selected:true};
const fragment={...source,citation:`document:${hash}:1:0`,locator:'第1页',unit:1,chunk:0,text:'<script>越权</script>',method:'ocr',confidence:.4};
const preview={mode:'summary' as const,question:'概括',supplier:'Main · deepseek-flash · https://api.deepseek.com',fragments:[fragment],coverage:[coverage],revision:hash};

describe('M15 明确正文发送和模型结果边界',()=>{
  it('主进程请求只允许证据身份、问题和已预览版本',()=>{
    const request={id,mode:'summary',question:'概括',sources:[source]};
    expect(chatSynthesisPreviewSchema.safeParse(request).success).toBe(true);
    expect(chatSynthesisGenerateSchema.safeParse({...request,revision:hash,request_id:id}).success).toBe(true);
    for(const extra of [{path:'C:/secret.txt'},{content:'hidden'},{model:'other'},{url:'https://invalid.example'},{approved:true}])
      expect(chatSynthesisGenerateSchema.safeParse({...request,revision:hash,request_id:id,...extra}).success).toBe(false);
    expect(chatSynthesisPreviewSchema.safeParse({...request,sources:Array(4).fill(source)}).success).toBe(false);
    expect(chatSynthesisGenerateSchema.safeParse({...request,revision:'old',request_id:id}).success).toBe(false);
  });
  it('预览纯文本展示精确片段、截断与 OCR 风险',()=>{
    expect(synthesisPreviewSchema.safeParse(preview).success).toBe(true);
    const html=renderToStaticMarkup(React.createElement(SynthesisPreviewCard,{preview,disabled:false,confirm:()=>{},close:()=>{}}));
    expect(html).toContain('&lt;script&gt;');expect(html).not.toContain('<script>');
    expect(html).toContain('1/3');expect(html).toContain('来源含 OCR');expect(html).toContain('确认这些片段');
  });
  it('生成消息需有完整契约，引用可回查且外部文字不执行',()=>{
    const data={answer:'<img src=x>',claims:[{text:'OCR待核对',kind:'inference',citations:[fragment.citation]}],
      citations:[Object.fromEntries(Object.entries(fragment).filter(([key])=>key!=='text'))],coverage,revision:hash,model:'deepseek-flash',usage:{total_tokens:30}};
    const message={id,role:'assistant' as const,kind:'synthesis' as const,text:'模型回答',created_at:'2026-09-29',data:{...data,coverage:[coverage]}};
    expect(chatMessageSchema.safeParse(message).success).toBe(true);
    expect(chatMessageSchema.safeParse({...message,data:{answer:'x'}}).success).toBe(false);
    const html=renderToStaticMarkup(React.createElement(SynthesisResult,{message,show:()=>{}}));
    expect(html).toContain('&lt;img src=x&gt;');expect(html).not.toContain('<img');expect(html).toContain('引用版本与覆盖范围');
  });
});
