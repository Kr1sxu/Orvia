import {describe,it,expect} from 'vitest';
import {skillRun,skillToggle} from '../src/main/skills-contracts';
import {skillList,skillPlan,skillExecution} from '../src/main/skills-contracts';

describe('V4-002 固定工作流契约',()=>{
  it('renderer不能传入包路径、目录授权或原生批准',()=>{
    const input={skill_id:'file-organize',inputs:{path:'.'}};
    expect(skillRun.parse(input)).toEqual(input);
    for(const extra of [{root:'C:/private'},{grant_id:'synthetic'},{approved:true},{method:'computer.execute'},{path:'package'}])expect(skillRun.safeParse({...input,...extra}).success).toBe(false);
    expect(skillToggle.safeParse({skill_id:'file-organize',enabled:'true'}).success).toBe(false);
    expect(skillRun.safeParse({skill_id:'../code',inputs:{}}).success).toBe(false);
  });
  it('响应校验拒绝空壳完成和任意扩展字段',()=>{
    expect(skillExecution.safeParse({status:'completed'}).success).toBe(false);
    expect(skillList.safeParse({skills:[],password:'synthetic'}).success).toBe(false);
    expect(skillPlan.safeParse({status:'planned',approved:true}).success).toBe(false);
  });
});
