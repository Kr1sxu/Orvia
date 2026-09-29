import {describe,it,expect} from 'vitest';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {chatPublicationPreviewSchema,chatPublicationSaveSchema,publicationPreviewSchema,chatMessageSchema} from '../src/main/chat-contracts';
import {PublicationResult} from '../src/renderer/PublicationCards';

const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c',hash='a'.repeat(64);
const request={id,message_id:id,format:'pdf' as const,title:'合成简报',answer:'已核对内容',claim_texts:['结论文字']};

describe('M16 成品预览和保存边界',()=>{
  it('固定接口不接受路径、模板、模型或引用替换字段',()=>{
    expect(chatPublicationPreviewSchema.safeParse(request).success).toBe(true);
    expect(chatPublicationSaveSchema.safeParse({...request,revision:hash,request_id:id}).success).toBe(true);
    for(const extra of [{path:'C:/secret.pdf'},{template:'other.docx'},{model:'other'},{citations:['fake']},{approved:true}])
      expect(chatPublicationSaveSchema.safeParse({...request,revision:hash,request_id:id,...extra}).success).toBe(false);
    expect(chatPublicationPreviewSchema.safeParse({...request,title:'x'.repeat(41)}).success).toBe(false);
    expect(chatPublicationPreviewSchema.safeParse({...request,claim_texts:[]}).success).toBe(false);
  });
  it('预览契约保留页面和完整引用，结果只显示核验文件名',()=>{
    const reference={number:1,citation:`document:${hash}:1:0`,title:'<img src=x>',locator:'第1页',kind:'document' as const,evidence_id:hash};
    const preview={schema:'orvia.publication.v1',format:'pdf',message_id:id,title:'合成简报',answer:'已核对内容',claims:[{kind:'fact',label:'证据陈述',text:'结论文字',numbers:[1]}],references:[reference],pages:[{heading:'结论 1',body:'结论文字',label:'证据陈述',numbers:[1]},{heading:'来源与引用',body:'',label:'需核对',numbers:[],references:[reference]}],notice:'请核对',source_revision:hash,revision:hash,filename:'Orvia-brief.pdf'};
    expect(publicationPreviewSchema.safeParse(preview).success).toBe(true);
    const message={id,role:'system',kind:'publication',text:'已创建',created_at:'2026-09-29',data:{filename:'brief.pdf',format:'pdf',revision:hash,message_id:id,source_revision:hash,pages:2}};
    expect(chatMessageSchema.safeParse(message).success).toBe(true);
    const html=renderToStaticMarkup(React.createElement(PublicationResult,{message:chatMessageSchema.parse(message)}));
    expect(html).toContain('brief.pdf');expect(html).not.toContain('C:/');
  });
});
